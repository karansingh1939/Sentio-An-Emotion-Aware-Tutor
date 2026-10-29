"""Ownership checks in the same transaction that publishes a drawing."""

from contextlib import contextmanager

from sqlalchemy import text

from sentio.repositories.practice import PracticeRepository


class WhiteboardRepository:
    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def publication(self, owner, session_id, board_id):
        with PracticeRepository(self.engine).publication(
            None, None, student_id=owner
        ) as connection:
            if not connection.execute(
                text("SELECT 1 FROM sessions WHERE session_id=:session AND student_id=:owner"),
                {"session": session_id, "owner": owner},
            ).scalar():
                raise PermissionError("Study session is no longer available.")
            existing = connection.execute(
                text("SELECT student_id,session_id FROM whiteboards WHERE whiteboard_id=:board"),
                {"board": board_id},
            ).first()
            if existing and (existing[0] != owner or existing[1] != session_id):
                raise PermissionError("Canvas belongs to a different account or study session.")
            yield connection
