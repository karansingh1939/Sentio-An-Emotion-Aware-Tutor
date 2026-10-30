"""Owner-scoped topic maps of lectures, with each topic's practice state."""

import uuid
from pathlib import Path

from sqlalchemy import text

from sentio.study.topics import build_topics, is_weak, topic_state


class TopicRepository:
    def __init__(self, engine):
        self.engine = engine

    def _document(self, connection, owner, document_id):
        row = (
            connection.execute(
                text(
                    "SELECT id,filename,checksum,course_id FROM documents WHERE id=:id AND student_id=:owner AND status='indexed'"
                ),
                {"id": document_id, "owner": owner},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def _pages(self, connection, document_id):
        pages = {}
        for page, content in connection.execute(
            text(
                "SELECT COALESCE(page_number,1),text_content FROM document_chunks WHERE document_id=:id ORDER BY 1,chunk_index"
            ),
            {"id": document_id},
        ):
            pages.setdefault(page, []).append(content)
        return [(page, "\n".join(parts)) for page, parts in sorted(pages.items())]

    def _topics(self, connection, owner, document):
        """The document's stored topics, rebuilt when the lecture file has changed."""
        rows = [
            dict(row)
            for row in connection.execute(
                text(
                    "SELECT id,title,first_page,last_page,checksum FROM note_topics WHERE document_id=:id AND student_id=:owner ORDER BY position"
                ),
                {"id": document["id"], "owner": owner},
            ).mappings()
        ]
        if rows and all(row["checksum"] == document["checksum"] for row in rows):
            return rows
        connection.execute(
            text("DELETE FROM note_topics WHERE document_id=:id AND student_id=:owner"),
            {"id": document["id"], "owner": owner},
        )
        built = build_topics(
            self._pages(connection, document["id"]), Path(document["filename"]).stem
        )
        rows = []
        for position, topic in enumerate(built):
            row = {"id": str(uuid.uuid4()), **topic, "checksum": document["checksum"]}
            connection.execute(
                text(
                    "INSERT INTO note_topics VALUES (:id,:owner,:document,:title,:first_page,:last_page,:position,:checksum)"
                ),
                {**row, "owner": owner, "document": document["id"], "position": position},
            )
            rows.append(row)
        return rows

    def _results(self, connection, owner, document_ids):
        """Answers to page-attributed questions: {document_id: [(page, correct), ...]} in time order."""
        if not document_ids:
            return {}
        placeholders = ",".join(f":d{i}" for i in range(len(document_ids)))
        results = {}
        for document_id, page, correct in connection.execute(
            text(
                "SELECT q.source_document_id,q.source_page,a.correct FROM quiz_attempts a "
                "JOIN quiz_questions q ON q.question_id=a.question_id "
                f"WHERE a.student_id=:owner AND q.source_document_id IN ({placeholders}) "
                "ORDER BY a.timestamp,a.id"
            ),
            {"owner": owner, **{f"d{i}": d for i, d in enumerate(document_ids)}},
        ):
            results.setdefault(document_id, []).append((page, bool(correct)))
        return results

    def _lecture(self, connection, owner, document, results):
        topics = []
        for topic in self._topics(connection, owner, document):
            answers = [
                correct
                for page, correct in results.get(document["id"], [])
                if page is not None and topic["first_page"] <= page <= topic["last_page"]
            ]
            topics.append(
                {
                    "id": topic["id"],
                    "title": topic["title"],
                    "first_page": topic["first_page"],
                    "last_page": topic["last_page"],
                    "document_id": document["id"],
                    "filename": document["filename"],
                    **topic_state(answers),
                }
            )
        return {"document_id": document["id"], "filename": document["filename"], "topics": topics}

    def document_topics(self, owner, document_id):
        with self.engine.begin() as connection:
            document = self._document(connection, owner, document_id)
            if document is None:
                return None
            return self._lecture(
                connection, owner, document, self._results(connection, owner, [document_id])
            )

    def course_progress(self, owner, course_id):
        with self.engine.begin() as connection:
            if not connection.execute(
                text("SELECT 1 FROM courses WHERE id=:id AND student_id=:owner"),
                {"id": course_id, "owner": owner},
            ).first():
                return None
            ids = list(
                connection.execute(
                    text(
                        "SELECT id FROM documents WHERE course_id=:course AND student_id=:owner AND status='indexed' ORDER BY upload_date"
                    ),
                    {"course": course_id, "owner": owner},
                ).scalars()
            )
            results = self._results(connection, owner, ids)
            lectures = [
                self._lecture(connection, owner, self._document(connection, owner, i), results)
                for i in ids
            ]
        topics = [topic for lecture in lectures for topic in lecture["topics"]]
        summary = {
            state: sum(topic["state"] == state for topic in topics)
            for state in ("ready", "practising", "not_started")
        }
        weak = sorted(
            (topic for topic in topics if is_weak(topic)),
            key=lambda t: (t["recent_correct"] / t["recent_total"], -t["answers"]),
        )
        return {
            "course_id": course_id,
            "summary": {**summary, "total": len(topics)},
            "lectures": lectures,
            "weak": weak,
        }

    def rename(self, owner, topic_id, title):
        with self.engine.begin() as connection:
            result = connection.execute(
                text("UPDATE note_topics SET title=:title WHERE id=:id AND student_id=:owner"),
                {"id": topic_id, "owner": owner, "title": title},
            )
        return result.rowcount == 1

    def merge_into_previous(self, owner, topic_id):
        """Join a topic to the one before it; returns False if it is missing or first."""
        with self.engine.begin() as connection:
            topic = (
                connection.execute(
                    text(
                        "SELECT document_id,position,last_page FROM note_topics WHERE id=:id AND student_id=:owner"
                    ),
                    {"id": topic_id, "owner": owner},
                )
                .mappings()
                .first()
            )
            if topic is None:
                return False
            previous = connection.execute(
                text(
                    "SELECT id FROM note_topics WHERE document_id=:document AND student_id=:owner "
                    "AND position<:position ORDER BY position DESC LIMIT 1"
                ),
                {"document": topic["document_id"], "owner": owner, "position": topic["position"]},
            ).scalar()
            if previous is None:
                return False
            connection.execute(
                text("UPDATE note_topics SET last_page=:last WHERE id=:id"),
                {"id": previous, "last": topic["last_page"]},
            )
            connection.execute(text("DELETE FROM note_topics WHERE id=:id"), {"id": topic_id})
        return True

    def forget_document(self, document_id):
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM note_topics WHERE document_id=:id"), {"id": document_id}
            )
