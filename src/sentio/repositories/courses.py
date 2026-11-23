"""Owner-scoped courses: optional folders that group a student's lecture notes."""

import re
import time
import uuid

from sqlalchemy import text


class CourseConflict(ValueError):
    pass


class CourseRepository:
    def __init__(self, engine):
        self.engine = engine

    def list(self, owner):
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT c.id,c.name,c.created_at,COUNT(d.id) AS lecture_count FROM courses c "
                    "LEFT JOIN documents d ON d.course_id=c.id AND d.student_id=c.student_id "
                    "WHERE c.student_id=:owner GROUP BY c.id ORDER BY c.name COLLATE NOCASE"
                ),
                {"owner": owner},
            ).mappings()
            return [dict(row) for row in rows]

    def get(self, owner, course_id, connection=None):
        query = text("SELECT id,name,created_at FROM courses WHERE id=:id AND student_id=:owner")
        params = {"id": course_id, "owner": owner}
        if connection is not None:
            row = connection.execute(query, params).mappings().first()
        else:
            with self.engine.connect() as connection:
                row = connection.execute(query, params).mappings().first()
        return dict(row) if row else None

    def _check_name(self, connection, owner, name, course_id=None):
        clash = connection.execute(
            text(
                "SELECT 1 FROM courses WHERE student_id=:owner AND name=:name COLLATE NOCASE AND id!=:id"
            ),
            {"owner": owner, "name": name, "id": course_id or ""},
        ).first()
        if clash:
            raise CourseConflict("You already have a course with this name.")

    def create(self, owner, name):
        course = {"id": str(uuid.uuid4()), "name": name, "created_at": time.time()}
        with self.engine.begin() as connection:
            self._check_name(connection, owner, name)
            connection.execute(
                text("INSERT INTO courses VALUES (:id,:owner,:name,:created_at)"),
                {**course, "owner": owner},
            )
        return {**course, "lecture_count": 0}

    def rename(self, owner, course_id, name):
        with self.engine.begin() as connection:
            if self.get(owner, course_id, connection) is None:
                return None
            self._check_name(connection, owner, name, course_id)
            connection.execute(
                text("UPDATE courses SET name=:name WHERE id=:id AND student_id=:owner"),
                {"id": course_id, "owner": owner, "name": name},
            )
        return self.get(owner, course_id)

    def delete(self, owner, course_id):
        """Delete the course; its lectures stay, outside any course."""
        with self.engine.begin() as connection:
            if self.get(owner, course_id, connection) is None:
                return False
            connection.execute(
                text(
                    "UPDATE documents SET course_id=NULL WHERE course_id=:id AND student_id=:owner"
                ),
                {"id": course_id, "owner": owner},
            )
            connection.execute(
                text("DELETE FROM syllabus_items WHERE course_id=:id AND student_id=:owner"),
                {"id": course_id, "owner": owner},
            )
            connection.execute(
                text("DELETE FROM courses WHERE id=:id AND student_id=:owner"),
                {"id": course_id, "owner": owner},
            )
        return True

    def move_document(self, owner, document_id, course_id):
        with self.engine.begin() as connection:
            if course_id is not None and self.get(owner, course_id, connection) is None:
                return False
            result = connection.execute(
                text(
                    "UPDATE documents SET course_id=:course WHERE id=:document AND student_id=:owner"
                ),
                {"course": course_id, "document": document_id, "owner": owner},
            )
        return result.rowcount == 1

    def document_ids(self, owner, course_id, connection=None):
        query = text(
            "SELECT id FROM documents WHERE course_id=:course AND student_id=:owner ORDER BY upload_date"
        )
        params = {"course": course_id, "owner": owner}
        if connection is not None:
            return list(connection.execute(query, params).scalars())
        with self.engine.connect() as connection:
            return list(connection.execute(query, params).scalars())


COURSE_PREFIX = "course:"


def expand_source(connection, owner, source):
    """Resolve a "course:<id>" study source to that course's current document ids.

    Courses are resolved at use time, so lectures added later are included. Any other
    source ("all", a document id or a list) is returned unchanged.
    """
    if not (isinstance(source, str) and source.startswith(COURSE_PREFIX)):
        return source
    return list(
        connection.execute(
            text(
                "SELECT id FROM documents WHERE course_id=:course AND student_id=:owner ORDER BY upload_date"
            ),
            {"course": source[len(COURSE_PREFIX) :], "owner": owner},
        ).scalars()
    )


# "1. Introduction.pptx", "02_cnn.pdf", "Lecture 3", "L4 slides", "Week 5", "Unit 2".
LEADING_NUMBER = re.compile(r"^\s*(\d{1,3})(?!\d)")
NAMED_NUMBER = re.compile(
    r"\b(?:lecture|lec|l|week|wk|unit|class|module|session|chapter|ch|part)[\s._-]*(\d{1,3})(?!\d)",
    re.IGNORECASE,
)


def lecture_number(filename):
    """The lecture number a filename shows, or None when it shows none."""
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    match = LEADING_NUMBER.match(stem) or NAMED_NUMBER.search(stem)
    return int(match.group(1)) if match else None


def earlier_lectures(connection, owner, document_id):
    """The indexed lectures of the same course taught before this one, nearest first.

    Lectures that show a number ("3. CNN.pdf", "Lecture 3") are ordered by it. When the
    selected lecture shows none, upload order stands in for teaching order.
    """
    if not isinstance(document_id, str):
        return []
    rows = connection.execute(
        text(
            "SELECT d.id,d.filename,d.upload_date,d.status FROM documents d "
            "JOIN documents s ON s.course_id=d.course_id AND s.student_id=d.student_id "
            "WHERE s.id=:document AND s.student_id=:owner AND s.course_id IS NOT NULL"
        ),
        {"document": document_id, "owner": owner},
    ).mappings()
    lectures = [dict(row) for row in rows]
    selected = next((row for row in lectures if row["id"] == document_id), None)
    if selected is None:
        return []
    number = lecture_number(selected["filename"])
    if number is not None:
        earlier = [
            row
            for row in lectures
            if (row_number := lecture_number(row["filename"])) is not None and row_number < number
        ]
        earlier.sort(key=lambda row: -lecture_number(row["filename"]))
    else:
        earlier = [
            row for row in lectures if (row["upload_date"] or 0) < (selected["upload_date"] or 0)
        ]
        earlier.sort(key=lambda row: -(row["upload_date"] or 0))
    return [row["id"] for row in earlier if row["status"] == "indexed"]


def with_earlier_lectures(engine, owner, source):
    """A single lecture together with the course lectures taught before it.

    The tutor answers from earlier lectures too, so practice made from a session
    searches the same notes. Any other source is returned unchanged.
    """
    if not isinstance(source, str) or source in ("all", "none") or source.startswith(COURSE_PREFIX):
        return source
    with engine.connect() as connection:
        earlier = earlier_lectures(connection, owner, source)
    return [source, *earlier] if earlier else source
