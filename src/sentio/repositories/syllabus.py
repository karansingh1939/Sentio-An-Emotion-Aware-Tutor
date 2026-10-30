"""Owner-scoped course syllabi and their progress against the student's lecture topics.

Only the learner's corrections are stored: an item's link_mode is "auto" (match live
against current lecture topics), "manual" (linked_topic_id chosen by the learner) or
"none" (the learner says their notes don't cover it).
"""

import uuid

from sqlalchemy import text

from sentio.repositories.topics import TopicRepository
from sentio.study.syllabus import item_status, match, summarise


class SyllabusRepository:
    def __init__(self, engine):
        self.engine = engine

    def _owns_course(self, connection, owner, course_id):
        return connection.execute(
            text("SELECT 1 FROM courses WHERE id=:id AND student_id=:owner"),
            {"id": course_id, "owner": owner},
        ).first()

    def replace(self, owner, course_id, items):
        with self.engine.begin() as connection:
            if not self._owns_course(connection, owner, course_id):
                return False
            connection.execute(
                text("DELETE FROM syllabus_items WHERE course_id=:course AND student_id=:owner"),
                {"course": course_id, "owner": owner},
            )
            for position, item in enumerate(items):
                connection.execute(
                    text(
                        "INSERT INTO syllabus_items VALUES (:id,:owner,:course,:unit,:title,:position,'auto',NULL)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "owner": owner,
                        "course": course_id,
                        "unit": item["unit"],
                        "title": item["title"],
                        "position": position,
                    },
                )
        return True

    def delete(self, owner, course_id):
        with self.engine.begin() as connection:
            if not self._owns_course(connection, owner, course_id):
                return False
            connection.execute(
                text("DELETE FROM syllabus_items WHERE course_id=:course AND student_id=:owner"),
                {"course": course_id, "owner": owner},
            )
        return True

    def set_link(self, owner, item_id, mode, topic_id=None):
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    "UPDATE syllabus_items SET link_mode=:mode,linked_topic_id=:topic WHERE id=:id AND student_id=:owner"
                ),
                {"id": item_id, "owner": owner, "mode": mode, "topic": topic_id},
            )
        return result.rowcount == 1

    def progress(self, owner, course_id):
        """Syllabus items with their matched lecture topics, status and the course summary."""
        with self.engine.connect() as connection:
            if not self._owns_course(connection, owner, course_id):
                return None
            items = [
                dict(row)
                for row in connection.execute(
                    text(
                        "SELECT id,unit,title,link_mode,linked_topic_id FROM syllabus_items "
                        "WHERE course_id=:course AND student_id=:owner ORDER BY position"
                    ),
                    {"course": course_id, "owner": owner},
                ).mappings()
            ]
        lectures = TopicRepository(self.engine).course_progress(owner, course_id, with_text=True)
        topics = [topic for lecture in lectures["lectures"] for topic in lecture["topics"]]
        by_id = {topic["id"]: topic for topic in topics}
        for item in items:
            if item["link_mode"] == "none":
                linked = []
            elif item["link_mode"] == "manual" and item["linked_topic_id"] in by_id:
                linked = [item["linked_topic_id"]]
            else:  # auto, or a manual link whose topic was merged away
                linked = match(item["title"], topics)
            item["topics"] = [
                {key: by_id[topic_id][key] for key in _TOPIC_FIELDS} for topic_id in linked
            ]
            item["status"] = item_status([by_id[topic_id]["state"] for topic_id in linked])
        return {
            "course_id": course_id,
            "items": items,
            "summary": summarise([item["status"] for item in items]),
            "topics": [{key: topic[key] for key in _TOPIC_FIELDS} for topic in topics],
        }


_TOPIC_FIELDS = ("id", "title", "document_id", "filename", "first_page", "last_page", "state")
