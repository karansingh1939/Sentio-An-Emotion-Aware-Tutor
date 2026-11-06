"""Owner-scoped topic maps of lectures, with each topic's practice state."""

import time
import uuid
from pathlib import Path

from sqlalchemy import text

from sentio.flashcards import fsrs
from sentio.jobs.control import WorkInputError
from sentio.study.topics import build_topics, is_weak, topic_progress


class TopicChanged(WorkInputError):
    """A topic chosen for practice was merged away, or its lecture was replaced."""


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
            # Two requests can build the same map at once, and both answers must stay usable.
            identity = f"{owner}/{document['id']}/{document['checksum']}/{topic['first_page']}"
            row = {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, identity)),
                **topic,
                "checksum": document["checksum"],
            }
            connection.execute(
                text(
                    "INSERT INTO note_topics VALUES (:id,:owner,:document,:title,:first_page,:last_page,:position,:checksum)"
                ),
                {**row, "owner": owner, "document": document["id"], "position": position},
            )
            rows.append(row)
        return rows

    def _results(self, connection, owner, document_ids):
        """Reviews of page-attributed quiz questions and flashcards, in time order:
        {document_id: [(page, time, FSRS rating), ...]}."""
        if not document_ids:
            return {}
        placeholders = ",".join(f":d{i}" for i in range(len(document_ids)))
        params = {"owner": owner, **{f"d{i}": d for i, d in enumerate(document_ids)}}
        results = {}
        for document_id, page, when, correct in connection.execute(
            text(
                "SELECT q.source_document_id,q.source_page,a.timestamp,a.correct FROM quiz_attempts a "
                "JOIN quiz_questions q ON q.question_id=a.question_id "
                f"WHERE a.student_id=:owner AND q.source_document_id IN ({placeholders}) "
                "ORDER BY a.timestamp,a.id"
            ),
            params,
        ):
            rating = fsrs.GOOD if correct else fsrs.AGAIN
            results.setdefault(document_id, []).append((page, when, rating))
        for document_id, page, when, quality in connection.execute(
            text(
                "SELECT c.source_document_id,c.source_page,r.created_at,r.quality_score FROM card_reviews r "
                "JOIN flashcards c ON c.card_id=r.card_id "
                f"WHERE r.student_id=:owner AND c.source_document_id IN ({placeholders})"
            ),
            params,
        ):
            rating = fsrs.rating_from_quality(quality)
            results.setdefault(document_id, []).append((page, when, rating))
        for reviews in results.values():
            reviews.sort(key=lambda review: review[1])
        return results

    def _lecture(self, connection, owner, document, results, with_text=False):
        pages = dict(self._pages(connection, document["id"])) if with_text else {}
        now = time.time()
        topics = []
        for topic in self._topics(connection, owner, document):
            reviews = [
                (when, rating)
                for page, when, rating in results.get(document["id"], [])
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
                    **topic_progress(reviews, now),
                    **(
                        {
                            "text": "\n".join(
                                content
                                for page, content in pages.items()
                                if topic["first_page"] <= page <= topic["last_page"]
                            )
                        }
                        if with_text
                        else {}
                    ),
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

    def course_progress(self, owner, course_id, with_text=False):
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
                self._lecture(
                    connection, owner, self._document(connection, owner, i), results, with_text
                )
                for i in ids
            ]
        topics = [topic for lecture in lectures for topic in lecture["topics"]]
        summary = {
            state: sum(topic["state"] == state for topic in topics)
            for state in ("ready", "review_due", "practising", "not_started")
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
            "due": _due(topics),
        }

    def learning_path(self, owner, course_id=None, limit=12):
        """What to study next from the learner's own lectures: due reviews first (least
        remembered), then topics being practised, then new topics in lecture order."""
        with self.engine.begin() as connection:
            query = "SELECT id FROM documents WHERE student_id=:owner AND status='indexed'"
            params = {"owner": owner}
            if course_id:
                if not connection.execute(
                    text("SELECT 1 FROM courses WHERE id=:id AND student_id=:owner"),
                    {"id": course_id, "owner": owner},
                ).first():
                    return None
                query += " AND course_id=:course"
                params["course"] = course_id
            ids = list(connection.execute(text(query + " ORDER BY upload_date"), params).scalars())
            results = self._results(connection, owner, ids)
            lectures = [
                self._lecture(connection, owner, self._document(connection, owner, i), results)
                for i in ids
            ]
        topics = [topic for lecture in lectures for topic in lecture["topics"]]
        practising = [t for t in topics if t["state"] == "practising"]
        practising.sort(key=lambda t: t["recent_correct"] / max(1, t["recent_total"]))
        ordered = (
            [(t, "review", "Due for review: your memory of it is fading.") for t in _due(topics)]
            + [
                (t, "practise", "Practising: recent answers were not all right.")
                for t in practising
            ]
            + [
                (t, "learn", "Not started yet, next in lecture order.")
                for t in topics
                if t["state"] == "not_started"
            ]
        )
        keys = ("id", "title", "document_id", "filename", "first_page", "last_page", "state")
        return {
            "course_id": course_id,
            "total": len(topics),
            "ready": sum(t["state"] == "ready" for t in topics),
            "steps": [
                {**{k: t[k] for k in keys}, "action": action, "reason": reason}
                for t, action, reason in ordered[:limit]
            ],
        }

    def due_topics(self, owner):
        """Topics due for review across all the student's notes, least remembered first."""
        with self.engine.begin() as connection:
            ids = list(
                connection.execute(
                    text("SELECT id FROM documents WHERE student_id=:owner AND status='indexed'"),
                    {"owner": owner},
                ).scalars()
            )
            results = self._results(connection, owner, ids)
            lectures = [
                self._lecture(connection, owner, self._document(connection, owner, i), results)
                for i in results
            ]
        return _due(topic for lecture in lectures for topic in lecture["topics"])

    def passages(self, owner, topic_ids):
        """The chosen topics in order, each with its (page, text) pairs.

        None when any of them has gone: merged away, or its lecture replaced or removed.
        """
        topics = []
        with self.engine.connect() as connection:
            for topic_id in topic_ids:
                topic = (
                    connection.execute(
                        text(
                            "SELECT id,document_id,title,first_page,last_page,checksum FROM note_topics WHERE id=:id AND student_id=:owner"
                        ),
                        {"id": topic_id, "owner": owner},
                    )
                    .mappings()
                    .first()
                )
                document = topic and self._document(connection, owner, topic["document_id"])
                if not document or document["checksum"] != topic["checksum"]:
                    return None
                pages = [
                    (page, content)
                    for page, content in self._pages(connection, document["id"])
                    if topic["first_page"] <= page <= topic["last_page"]
                ]
                if not pages:
                    return None
                topics.append({**topic, "filename": document["filename"], "pages": pages})
        return topics

    def focus(self, session):
        """The topics a session practises, with their slides; [] when it has none."""
        topic_ids = session.metadata.get("topic_ids")
        if not topic_ids:
            return []
        topics = self.passages(session.student_id, topic_ids)
        if topics is None:
            raise TopicChanged("This topic changed. Open the course and choose it again.")
        return topics

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


def _due(topics):
    return sorted((t for t in topics if t["state"] == "review_due"), key=lambda t: t["recall"])
