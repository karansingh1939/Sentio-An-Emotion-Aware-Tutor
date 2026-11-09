import json
import logging
import time
import uuid
from contextlib import nullcontext
from datetime import datetime
from typing import Dict, List, Optional

from sentio.config import session_cfg
from sentio.repositories.sessions import SessionPersister
from sentio.session.analytics import SessionAnalytics, SessionAnalyticsEngine
from sentio.session.models import (
    EmotionEvent,
    QuizAttempt,
    Session,
    SessionStatus,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Main interface used by TutorAgent and the API layer.

    Manages the full lifecycle of tutoring sessions:
    create → record events → adapt → close → persist → report
    """

    def __init__(
        self,
        persister: Optional[SessionPersister] = None,
        analytics_engine: Optional[SessionAnalyticsEngine] = None,
    ):
        self._sessions: Dict[str, Session] = {}  # session_id → Session
        self.persister = persister or SessionPersister()
        self.analytics_engine = analytics_engine or SessionAnalyticsEngine()
        self._diagnostics: Dict[str, List[dict]] = {}

    def record_diagnostics(self, session_id: str, diagnostics: dict):
        if session_id not in self._diagnostics:
            self._diagnostics[session_id] = []
        self._diagnostics[session_id].append(diagnostics)
        self._diagnostics[session_id] = self._diagnostics[session_id][-200:]

    def get_diagnostics(self, session_id: str) -> List[dict]:
        return self._diagnostics.get(session_id, [])

    def load(self):
        self.persister.load()
        logger.info("SessionManager ready.")

    # ── Session Lifecycle ──────────────────────

    def create_session(
        self,
        student_id: str,
        subject: str,
        topic: str,
        difficulty: str = "beginner",
        metadata: Optional[dict] = None,
    ) -> Session:
        """Create and register a new active session."""
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            student_id=student_id,
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            metadata=metadata or {},
        )
        session.add_topic(topic)
        self._sessions[session_id] = session
        try:
            self.persister.save_session(session)
        except Exception as e:
            logger.warning(f"Failed to persist session {session_id[:8]} to SQLite: {e}")
        logger.info(
            f"Session created: {session_id[:8]}… | "
            f"student={student_id} | {subject}/{topic} [{difficulty}]"
        )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        if not session_id:
            return None
        if session_id in self._sessions:
            return self._sessions[session_id]

        data = self.persister.load_session_data(session_id)
        if data:
            session = Session(
                session_id=data["session_id"],
                student_id=data["student_id"],
                subject=data["subject"],
                topic=data["topic"],
                difficulty=data["difficulty"],
                status=SessionStatus(data["status"]),
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                closed_at=data["closed_at"],
                total_exchanges=data.get("total_exchanges", 0),
                total_tokens=data.get("total_tokens", 0),
                topics_covered=data.get("topics_covered", []),
                metadata=data.get("metadata", {}),
                summary=data.get("summary"),
            )
            session.response_latencies = data.get("response_latencies", [])

            from sqlalchemy import text

            with self.persister._engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT timestamp, topic, difficulty, correct, response_time_sec, question_text FROM quiz_attempts WHERE session_id = :sid ORDER BY timestamp, id"
                    ),
                    {"sid": session_id},
                ).fetchall()
            for row in rows:
                session.quiz_tracker.record(
                    QuizAttempt(
                        timestamp=row[0],
                        topic=row[1],
                        difficulty=row[2],
                        correct=bool(row[3]),
                        response_time_sec=row[4] or 0,
                        question_preview=row[5] or "",
                    )
                )

            # Cache in memory
            self._sessions[session_id] = session
            return session
        return None

    def get_or_raise(self, session_id: str) -> Session:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def pause_session(self, session_id: str):
        session = self.get_or_raise(session_id)
        session.status = SessionStatus.PAUSED
        self.persister.save_session(session)
        logger.info(f"Session paused: {session_id[:8]}…")

    def resume_session(self, session_id: str):
        session = self.get_or_raise(session_id)
        previous = session.status, session.closed_at, session.updated_at
        try:
            session.status = SessionStatus.ACTIVE
            session.closed_at = None
            session.touch()
            self.persister.save_owned_session(session)
        except Exception:
            session.status, session.closed_at, session.updated_at = previous
            raise
        logger.info(f"Session resumed: {session_id[:8]}…")

    def close_session(self, session_id: str) -> SessionAnalytics:
        """
        Close a session, compute final analytics, persist, and return report.
        """
        session = self.get_or_raise(session_id)
        session.status = SessionStatus.CLOSED
        session.closed_at = time.time()

        analytics = self.analytics_engine.compute(session)
        self.persister.save_session(session)

        # Save full emotion timeline separately
        self._save_emotion_log(session)

        # Purge real-time attention logs from the database
        try:
            self.clear_session_telemetry(session_id)
        except Exception as e:
            logger.error(
                f"Failed to clear session telemetry logs for {session_id[:8]} during cleanup: {e}",
                exc_info=True,
            )

        logger.info(f"Session closed: {session_id[:8]}… | {analytics.summary_text()}")
        return analytics

    def timeout_idle_sessions(self):
        """Call periodically to close sessions that have gone idle."""
        for sid, session in list(self._sessions.items()):
            if session.is_active and session.is_idle:
                session.status = SessionStatus.TIMEDOUT
                session.closed_at = time.time()
                self.persister.save_session(session)
                logger.warning(f"Session timed out: {sid[:8]}…")

    # ── Event Recording ────────────────────────

    def record_emotion(
        self,
        session_id: str,
        emotion_result,  # EmotionResult from sentio.emotion.detector
        strategy_active: str = "standard",
    ):
        """Record an emotion detection result. It informs tone only, never difficulty."""
        session = self.get_or_raise(session_id)
        if not session.is_active:
            return

        event = EmotionEvent(
            timestamp=time.time(),
            emotion=emotion_result.emotion,
            learning_state=emotion_result.learning_state,
            confidence=emotion_result.confidence,
            strategy_triggered=strategy_active,
        )
        session.emotion_timeline.record(event)
        session.touch()

    def record_quiz_attempt(
        self,
        session_id: str,
        correct: bool,
        topic: str = "",
        response_time_sec: float = 0.0,
        question_preview: str = "",
        difficulty: Optional[str] = None,
        connection=None,
        student_answer: str = "answered",
        score: Optional[float] = None,
        question_id: Optional[str] = None,
    ):
        """Record a quiz answer and update difficulty if needed."""
        session = self.get_or_raise(session_id)
        attempt = QuizAttempt(
            timestamp=time.time(),
            topic=topic or session.topic,
            difficulty=difficulty or session.difficulty,
            correct=correct,
            response_time_sec=response_time_sec,
            question_preview=question_preview,
        )
        session.quiz_tracker.record(attempt)
        session.touch()

        # 1. Update SQLite database table `quiz_attempts` if database is active
        self.ensure_student_exists(session.student_id, connection=connection)
        self.ensure_topic_exists(attempt.topic, connection=connection)
        from sqlalchemy import text

        with (
            nullcontext(connection) if connection is not None else self.persister._engine.connect()
        ) as conn:
            conn.execute(
                text("""
                    INSERT INTO quiz_attempts 
                    (session_id, student_id, topic, question_text, student_answer, 
                     correct, score, response_time_sec, difficulty, timestamp, question_id)
                    VALUES (:sid, :stud, :topic, :q_text, :ans, :correct, :score, :resp_time, :diff, :ts, :qid)
                """),
                {
                    "sid": session_id,
                    "stud": session.student_id,
                    "topic": attempt.topic,
                    "q_text": question_preview or "Quiz Question",
                    "ans": student_answer,
                    "correct": 1 if correct else 0,
                    "score": score if score is not None else (1.0 if correct else 0.0),
                    "resp_time": response_time_sec,
                    "diff": attempt.difficulty,
                    "ts": attempt.timestamp,
                    "qid": question_id,
                },
            )
            if connection is None:
                conn.commit()

        # 2. Update topic mastery automatically
        self.update_topic_mastery(
            student_id=session.student_id,
            topic_id=topic or session.topic,
            correct=correct,
            difficulty=attempt.difficulty,
            connection=connection,
        )

        # 3. Difficulty adaptation based on quiz performance
        change = self._maybe_adapt_difficulty(session)

        logger.debug(
            f"Quiz attempt | session={session_id[:8]} | "
            f"correct={correct} | streak_correct={session.quiz_tracker.consecutive_correct} "
            f"| streak_wrong={session.quiz_tracker.consecutive_wrong}"
        )
        return change

    def record_exchange(
        self,
        session_id: str,
        tokens: int = 0,
        latency_ms: float = 0.0,
        new_topic: Optional[str] = None,
    ):
        """Record that a tutor–student exchange occurred."""
        session = self.get_or_raise(session_id)
        session.record_exchange(tokens=tokens, latency_ms=latency_ms)
        if new_topic:
            session.add_topic(new_topic)

    # ── Difficulty Adaptation ──────────────────

    def _maybe_adapt_difficulty(self, session: Session):
        """Step the level after a quiz streak (sentio.tutor.difficulty), unless it is pinned.

        The streak restarts after a change, so one streak moves the level by one step.
        Returns the change for the learner to see, or None.
        """
        from sentio.tutor.difficulty import describe, step, streak_change

        qt = session.quiz_tracker
        change = streak_change(qt.consecutive_correct, qt.consecutive_wrong)
        if change is None or session.metadata.get("difficulty_pinned"):
            return None
        direction, reason = change
        previous = session.difficulty
        new_level = step(previous, direction)
        if new_level == previous:
            return None
        session.update_difficulty(new_level, reason)
        qt.consecutive_correct = qt.consecutive_wrong = 0
        return describe(previous, new_level, reason)

    # ── Queries & Analytics ────────────────────

    def get_analytics(self, session_id: str) -> SessionAnalytics:
        """Compute live analytics for an active or closed session."""
        session = self.get_or_raise(session_id)
        return self.analytics_engine.compute(session)

    def get_current_state(self, session_id: str) -> dict:
        """
        Lightweight state snapshot used by TutorAgent on every exchange.
        """
        session = self.get_or_raise(session_id)
        tl = session.emotion_timeline
        qt = session.quiz_tracker
        return {
            "session_id": session.session_id,
            "subject": session.subject,
            "topic": session.topic,
            "difficulty": session.difficulty,
            "learning_state": session.current_learning_state,
            "strategy": session.current_strategy,
            "dominant_state": tl.dominant_state(),
            "engagement_score": tl.engagement_score(),
            "consecutive_correct": qt.consecutive_correct,
            "consecutive_wrong": qt.consecutive_wrong,
            "quiz_accuracy": qt.accuracy,
            "total_exchanges": session.total_exchanges,
            "duration_minutes": session.duration_minutes,
            "topics_covered": session.topics_covered,
            "status": session.status.value,
            "metadata": session.metadata,
        }

    def list_sessions(
        self, student_id: Optional[str] = None, active_only: bool = False
    ) -> List[dict]:
        """
        List sessions. If active_only, return from in-memory store.
        Otherwise include persisted sessions.
        """
        if active_only:
            sessions = [s.to_dict() for s in self._sessions.values() if s.is_active]
            if student_id:
                sessions = [s for s in sessions if s["student_id"] == student_id]
            return sessions
        return self.persister.list_sessions(student_id=student_id)

    def get_student_history(self, student_id: str, limit: int = 20) -> List[dict]:
        """Return past session summaries for a student."""
        return self.persister.list_sessions(student_id=student_id, limit=limit)

    # ── Student Memory System ──────────────────

    def ensure_student_exists(self, student_id: str, connection=None):
        from sqlalchemy import text

        with (
            nullcontext(connection) if connection is not None else self.persister._engine.connect()
        ) as conn:
            row = conn.execute(
                text("SELECT student_id FROM students WHERE student_id = :sid"), {"sid": student_id}
            ).fetchone()
            if not row:
                conn.execute(
                    text(
                        "INSERT INTO students (student_id, created_at, metadata_json) VALUES (:sid, :created, :meta)"
                    ),
                    {"sid": student_id, "created": time.time(), "meta": json.dumps({})},
                )
                if connection is None:
                    conn.commit()

    def ensure_topic_exists(self, topic_id: str, subject: str = "general", connection=None):
        from sqlalchemy import text

        with (
            nullcontext(connection) if connection is not None else self.persister._engine.connect()
        ) as conn:
            row = conn.execute(
                text("SELECT topic_id FROM topics WHERE topic_id = :tid"), {"tid": topic_id}
            ).fetchone()
            if not row:
                conn.execute(
                    text(
                        "INSERT INTO topics (topic_id, subject, display_name, description) VALUES (:tid, :sub, :name, :desc)"
                    ),
                    {
                        "tid": topic_id,
                        "sub": subject,
                        "name": topic_id.replace("_", " ").title(),
                        "desc": "",
                    },
                )
                if connection is None:
                    conn.commit()

    def update_topic_mastery(
        self,
        student_id: str,
        topic_id: str,
        correct: bool,
        difficulty: str = "intermediate",
        connection=None,
    ):
        self.ensure_student_exists(student_id, connection=connection)
        self.ensure_topic_exists(topic_id, connection=connection)
        from sqlalchemy import text

        from sentio.config import mastery_cfg

        alpha = mastery_cfg.SMOOTHING_FACTOR
        weight = mastery_cfg.DIFFICULTY_WEIGHTS.get(difficulty, 1.0)
        with (
            nullcontext(connection) if connection is not None else self.persister._engine.connect()
        ) as conn:
            row = conn.execute(
                text(
                    "SELECT mastery_score, attempts_count, consecutive_correct FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": student_id, "tid": topic_id},
            ).fetchone()
            if row:
                old_mastery, attempts, consec = row
                attempts += 1
                if correct:
                    consec = consec + 1 if consec >= 0 else 1
                else:
                    consec = consec - 1 if consec <= 0 else -1
            else:
                old_mastery = 0.0
                attempts = 1
                consec = 1 if correct else -1
            attempt_score = 1.0 if correct else 0.0
            new_mastery = old_mastery + alpha * weight * (attempt_score - old_mastery)
            new_mastery = max(0.0, min(1.0, new_mastery))
            if row:
                conn.execute(
                    text(
                        "UPDATE student_knowledge SET mastery_score = :mast, attempts_count = :att, consecutive_correct = :consec, last_attempt_at = :lat WHERE student_id = :sid AND topic_id = :tid"
                    ),
                    {
                        "mast": new_mastery,
                        "att": attempts,
                        "consec": consec,
                        "lat": time.time(),
                        "sid": student_id,
                        "tid": topic_id,
                    },
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO student_knowledge (student_id, topic_id, mastery_score, attempts_count, consecutive_correct, last_attempt_at) VALUES (:sid, :tid, :mast, :att, :consec, :lat)"
                    ),
                    {
                        "sid": student_id,
                        "tid": topic_id,
                        "mast": new_mastery,
                        "att": attempts,
                        "consec": consec,
                        "lat": time.time(),
                    },
                )
            if connection is None:
                conn.commit()
            logger.info(
                f"Updated mastery for student {student_id} on topic {topic_id}: {old_mastery:.3f} -> {new_mastery:.3f}"
            )

    def get_weak_topics(self, student_id: str) -> List[dict]:
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT sk.topic_id, sk.mastery_score, t.display_name FROM student_knowledge sk JOIN topics t ON sk.topic_id = t.topic_id WHERE sk.student_id = :sid AND sk.mastery_score < 0.5"
                ),
                {"sid": student_id},
            ).fetchall()
        return [{"topic_id": r[0], "mastery_score": r[1], "display_name": r[2]} for r in rows]

    def get_strong_topics(self, student_id: str) -> List[dict]:
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT sk.topic_id, sk.mastery_score, t.display_name FROM student_knowledge sk JOIN topics t ON sk.topic_id = t.topic_id WHERE sk.student_id = :sid AND sk.mastery_score >= 0.8"
                ),
                {"sid": student_id},
            ).fetchall()
        return [{"topic_id": r[0], "mastery_score": r[1], "display_name": r[2]} for r in rows]

    def add_learning_goal(
        self,
        student_id: str,
        goal_text: str,
        topic_id: Optional[str] = None,
        target_date: Optional[float] = None,
    ) -> str:
        self.ensure_student_exists(student_id)
        if topic_id:
            self.ensure_topic_exists(topic_id)
        goal_id = str(uuid.uuid4())
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            conn.execute(
                text(
                    "INSERT INTO learning_goals (goal_id, student_id, topic_id, goal_text, target_date, status, created_at) VALUES (:gid, :sid, :tid, :txt, :tgt, 'active', :created)"
                ),
                {
                    "gid": goal_id,
                    "sid": student_id,
                    "tid": topic_id,
                    "txt": goal_text,
                    "tgt": target_date,
                    "created": time.time(),
                },
            )
            conn.commit()
        return goal_id

    def get_learning_goals(self, student_id: str, status: str = "active") -> List[dict]:
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT goal_id, topic_id, goal_text, target_date, status, created_at, completed_at FROM learning_goals WHERE student_id = :sid AND status = :status"
                ),
                {"sid": student_id, "status": status},
            ).fetchall()
        return [
            {
                "goal_id": r[0],
                "topic_id": r[1],
                "goal_text": r[2],
                "target_date": r[3],
                "status": r[4],
                "created_at": r[5],
                "completed_at": r[6],
            }
            for r in rows
        ]

    def get_student_mistake_metrics(self, student_id: str) -> dict:
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            recent_rows = conn.execute(
                text(
                    "SELECT topic, question_text, difficulty, timestamp FROM quiz_attempts WHERE student_id = :sid AND correct = 0 ORDER BY timestamp DESC LIMIT 5"
                ),
                {"sid": student_id},
            ).fetchall()
            recent_mistakes = [
                {"topic": r[0], "question_text": r[1], "difficulty": r[2], "timestamp": r[3]}
                for r in recent_rows
            ]
            recurring_rows = conn.execute(
                text(
                    "SELECT topic, COUNT(*) as fail_count FROM quiz_attempts WHERE student_id = :sid AND correct = 0 GROUP BY topic HAVING COUNT(*) > 1 ORDER BY fail_count DESC"
                ),
                {"sid": student_id},
            ).fetchall()
            recurring_mistakes = [{"topic": r[0], "fail_count": r[1]} for r in recurring_rows]
            freq_rows = conn.execute(
                text(
                    "SELECT topic, SUM(CASE WHEN correct = 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), COUNT(*) FROM quiz_attempts WHERE student_id = :sid GROUP BY topic"
                ),
                {"sid": student_id},
            ).fetchall()
            mistake_frequency = {
                r[0]: {"frequency": round(r[1], 3) if r[1] is not None else 0.0, "attempts": r[2]}
                for r in freq_rows
            }
        return {
            "recent_mistakes_list": recent_mistakes,
            "recurring_mistakes": recurring_mistakes,
            "mistake_frequency": mistake_frequency,
        }

    def get_student_memory_context(self, student_id: str) -> str:
        self.ensure_student_exists(student_id)
        weak_topics = self.get_weak_topics(student_id)
        strong_topics = self.get_strong_topics(student_id)
        goals = self.get_learning_goals(student_id, status="active")
        mistakes = self.get_student_mistake_metrics(student_id)
        lines = [
            "==================================================",
            f"STUDENT HISTORY & MEMORY CONTEXT (Student: {student_id})",
            "==================================================",
        ]
        if goals:
            lines.append("\nActive Learning Goals:")
            for g in goals:
                tgt_str = (
                    f" (target: {datetime.fromtimestamp(g['target_date']).strftime('%Y-%m-%d')})"
                    if g["target_date"]
                    else ""
                )
                lines.append(f" - {g['goal_text']}{tgt_str}")
        else:
            lines.append("\nNo active learning goals.")
        if strong_topics:
            lines.append("\nStrong Topics (Mastery >= 80%):")
            lines.append(
                " "
                + ", ".join(
                    [f"{t['display_name']} ({t['mastery_score']:.0%})" for t in strong_topics]
                )
            )
        if weak_topics:
            lines.append("\nWeak Topics (Mastery < 50%):")
            lines.append(
                " "
                + ", ".join(
                    [f"{t['display_name']} ({t['mastery_score']:.0%})" for t in weak_topics]
                )
            )
        recent_m = mistakes.get("recent_mistakes_list", [])
        if recent_m:
            lines.append("\nRecent Incorrect Quiz Answers:")
            for m in recent_m:
                lines.append(f' - [{m["topic"]} ({m["difficulty"]})]: "{m["question_text"]}"')
        recurring_m = mistakes.get("recurring_mistakes", [])
        if recurring_m:
            lines.append("\nTopics with Recurring Struggles:")
            for rm in recurring_m:
                lines.append(f" - {rm['topic']} ({rm['fail_count']} wrong answers)")
        mistake_freq = mistakes.get("mistake_frequency", {})
        if mistake_freq:
            lines.append("\nMistake Frequency by Topic:")
            for topic, metrics in mistake_freq.items():
                lines.append(
                    f" - {topic}: {metrics['frequency']:.1%} incorrect (out of {metrics['attempts']} attempts)"
                )
        lines.append("==================================================")
        return "\n".join(lines)

    # ── Document Management ───────────────────

    def register_document(self, doc: dict) -> bool:
        return self.persister.register_document(doc)

    def get_document_by_checksum(
        self, checksum: str, student_id: Optional[str] = None
    ) -> Optional[dict]:
        return self.persister.get_document_by_checksum(checksum, student_id=student_id)

    def get_document_by_filename(
        self, filename: str, student_id: Optional[str] = None, category: Optional[str] = None
    ) -> Optional[dict]:
        return self.persister.get_document_by_filename(
            filename, student_id=student_id, category=category
        )

    def delete_document(self, doc_id: str) -> bool:
        return self.persister.delete_document(doc_id)

    def list_documents(self, student_id: Optional[str] = None) -> List[dict]:
        return self.persister.list_documents(student_id=student_id)

    def save_document_chunks(self, doc_id: str, chunks: List[dict]) -> bool:
        return self.persister.save_document_chunks(doc_id, chunks)

    def get_document_chunks(self, doc_id: str) -> List[dict]:
        return self.persister.get_document_chunks(doc_id)

    def get_all_chunks(self) -> List[dict]:
        return self.persister.get_all_chunks()

    def clear_all_documents_and_chunks(self) -> bool:
        return self.persister.clear_all_documents_and_chunks()

    # ── Telemetry Database Helpers ────────────

    def save_attention_log(
        self,
        session_id: str,
        attention_score: float,
        focused: int,
        eye_openness: float,
        head_pose_pitch: float,
        head_pose_yaw: float,
        emotion: str,
    ):
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO attention_logs 
                    (session_id, timestamp, emotion, attention_score, focused, eye_openness, head_pose_pitch, head_pose_yaw)
                    VALUES (:sessid, :ts, :emotion, :score, :focused, :eye, :pitch, :yaw)
                """),
                {
                    "sessid": session_id,
                    "ts": time.time(),
                    "emotion": emotion,
                    "score": attention_score,
                    "focused": focused,
                    "eye": eye_openness,
                    "pitch": head_pose_pitch,
                    "yaw": head_pose_yaw,
                },
            )
            conn.commit()

    def get_attention_logs(self, session_id: str) -> List[dict]:
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT timestamp, emotion, attention_score, focused, eye_openness, head_pose_pitch, head_pose_yaw
                    FROM attention_logs WHERE session_id = :sid ORDER BY timestamp ASC
                """),
                {"sid": session_id},
            ).fetchall()
            return [
                {
                    "timestamp": r[0],
                    "emotion": r[1],
                    "attention_score": r[2],
                    "focused": r[3],
                    "eye_openness": r[4],
                    "head_pose_pitch": r[5],
                    "head_pose_yaw": r[6],
                }
                for r in rows
            ]

    def get_attention_summary(self, session_id: str) -> dict:
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT attention_score, focused, eye_openness, head_pose_pitch, head_pose_yaw, emotion
                    FROM attention_logs WHERE session_id = :sid ORDER BY timestamp ASC
                """),
                {"sid": session_id},
            ).fetchall()

            if not rows:
                return {
                    "count": 0,
                    "avg_attention": 0.0,
                    "focus_rate": 0.0,
                    "avg_eye_openness": 0.0,
                    "avg_pitch": 0.0,
                    "avg_yaw": 0.0,
                    "recent_state": "unknown",
                }

            count = len(rows)
            avg_attention = sum(r[0] for r in rows) / count
            focus_rate = sum(r[1] for r in rows) / count
            avg_eye_openness = (
                sum(r[2] for r in rows if r[2] is not None)
                / sum(1 for r in rows if r[2] is not None)
                if any(r[2] is not None for r in rows)
                else 0.0
            )
            avg_pitch = (
                sum(r[3] for r in rows if r[3] is not None)
                / sum(1 for r in rows if r[3] is not None)
                if any(r[3] is not None for r in rows)
                else 0.0
            )
            avg_yaw = (
                sum(r[4] for r in rows if r[4] is not None)
                / sum(1 for r in rows if r[4] is not None)
                if any(r[4] is not None for r in rows)
                else 0.0
            )
            recent_state = rows[-1][5]

            return {
                "count": count,
                "avg_attention": round(avg_attention, 4),
                "focus_rate": round(focus_rate, 4),
                "avg_eye_openness": round(avg_eye_openness, 4),
                "avg_pitch": round(avg_pitch, 4),
                "avg_yaw": round(avg_yaw, 4),
                "recent_state": recent_state,
            }

    def clear_session_telemetry(self, session_id: str):
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            conn.execute(
                text("DELETE FROM attention_logs WHERE session_id = :sid"), {"sid": session_id}
            )
            conn.commit()

    # ── Persistence Helpers ────────────────────

    def save_all_active(self):
        """Checkpoint all active sessions (call on shutdown)."""
        for session in self._sessions.values():
            if session.is_active:
                self.persister.save_session(session)
        logger.info(f"Checkpointed {len(self._sessions)} active sessions.")

    def _save_emotion_log(self, session: Session):
        """Persist full emotion timeline to a separate JSON file."""
        log_dir = session_cfg.EMOTION_LOG_PATH
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"{session.session_id}_emotions.json"
        with open(path, "w") as f:
            json.dump(session.emotion_timeline.all_as_dicts(), f, indent=2)

    def save_quiz(
        self,
        quiz_id: str,
        student_id: str,
        session_id: Optional[str],
        title: str,
        questions: List[dict],
        connection=None,
        provenance: Optional[dict] = None,
    ):
        import json

        from sqlalchemy import text

        with (
            nullcontext(connection)
            if connection is not None
            else self.persister._engine.connect() as conn
        ):
            # Verify session_id exists to avoid foreign key orphan records
            if session_id:
                s_check = conn.execute(
                    text("SELECT 1 FROM sessions WHERE session_id = :sid"), {"sid": session_id}
                ).fetchone()
                if not s_check:
                    session_id = None

            conn.execute(
                text("""
                    INSERT INTO quizzes (quiz_id, student_id, session_id, title, created_at, provenance_json)
                    VALUES (:qid, :sid, :sessid, :title, :ts, :provenance)
                """),
                {
                    "qid": quiz_id,
                    "sid": student_id,
                    "sessid": session_id,
                    "title": title,
                    "ts": time.time(),
                    "provenance": json.dumps(provenance) if provenance else None,
                },
            )
            for i, q in enumerate(questions):
                q_id = q.get("question_id") or f"{quiz_id}_q{i}"
                conn.execute(
                    text("""
                        INSERT INTO quiz_questions 
                        (question_id, quiz_id, question_text, question_type, options_json, correct_answer, explanation, difficulty, topic, source_document_id, source_page)
                        VALUES (:qid, :quiz_id, :text, :type, :opts, :correct, :exp, :diff, :topic, :source_document, :source_page)
                    """),
                    {
                        "qid": q_id,
                        "quiz_id": quiz_id,
                        "text": q["question_text"],
                        "type": q["question_type"],
                        "opts": json.dumps(q.get("options")) if q.get("options") else None,
                        "correct": q["correct_answer"],
                        "exp": q["explanation"],
                        "diff": q.get("difficulty", "intermediate"),
                        "topic": q.get("topic", "general"),
                        "source_document": q.get("source_document_id"),
                        "source_page": q.get("source_page"),
                    },
                )
            if connection is None:
                conn.commit()

    def get_quiz(self, quiz_id: str) -> Optional[dict]:
        import json

        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            q_row = conn.execute(
                text(
                    "SELECT title, student_id, session_id, revision, provenance_json FROM quizzes WHERE quiz_id = :qid"
                ),
                {"qid": quiz_id},
            ).fetchone()
            if not q_row:
                return None
            title, student_id, session_id, revision, provenance = q_row

            q_rows = conn.execute(
                text("""
                    SELECT question_text, question_type, options_json, correct_answer, explanation, difficulty, topic, question_id
                    FROM quiz_questions WHERE quiz_id = :qid ORDER BY rowid
                """),
                {"qid": quiz_id},
            ).fetchall()

            questions = []
            for r in q_rows:
                questions.append(
                    {
                        "question_text": r[0],
                        "question_type": r[1],
                        "options": json.loads(r[2]) if r[2] else None,
                        "correct_answer": r[3],
                        "explanation": r[4],
                        "difficulty": r[5],
                        "topic": r[6],
                        "question_id": r[7],
                    }
                )

            return {
                "quiz_id": quiz_id,
                "student_id": student_id,
                "session_id": session_id,
                "title": title,
                "questions": questions,
                "revision": revision or 0,
                "provenance": json.loads(provenance) if provenance else None,
            }

    def save_flashcard_deck(self, deck_id: str, student_id: str, deck_name: str):
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO flashcard_decks (deck_id, student_id, deck_name, created_at)
                    VALUES (:did, :sid, :name, :ts)
                """),
                {"did": deck_id, "sid": student_id, "name": deck_name, "ts": time.time()},
            )
            conn.commit()

    def list_flashcard_decks(self, student_id: str) -> List[dict]:
        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT deck_id, deck_name, created_at
                    FROM flashcard_decks WHERE student_id = :sid
                """),
                {"sid": student_id},
            ).fetchall()
            return [{"deck_id": r[0], "deck_name": r[1], "created_at": r[2]} for r in result]

    def save_flashcards(
        self,
        cards: List[dict],
        student_id: str,
        topic_id: str,
        deck_id: str,
        connection=None,
        provenance: Optional[dict] = None,
    ):
        import json
        import uuid

        from sqlalchemy import text

        with (
            nullcontext(connection)
            if connection is not None
            else self.persister._engine.connect() as conn
        ):
            self.ensure_student_exists(student_id, connection=conn)
            self.ensure_topic_exists(topic_id, connection=conn)
            for c in cards:
                card_id = str(uuid.uuid4())
                conn.execute(
                    text("""
                        INSERT INTO flashcards 
                        (card_id, student_id, topic_id, deck_id, front_text, back_text, created_at, interval_days, repetition_count, ease_factor, next_review_at, tags, provenance_json, source_document_id, source_page)
                        VALUES (:cid, :sid, :tid, :did, :front, :back, :ts, 0, 0, 2.5, :next_ts, :tags, :provenance, :source_document, :source_page)
                    """),
                    {
                        "cid": card_id,
                        "sid": student_id,
                        "tid": topic_id,
                        "did": deck_id,
                        "front": c["front"],
                        "back": c["back"],
                        "ts": time.time(),
                        "next_ts": time.time(),
                        "tags": json.dumps(c.get("tags", [])),
                        "provenance": json.dumps(provenance) if provenance else None,
                        "source_document": c.get("source_document_id"),
                        "source_page": c.get("source_page"),
                    },
                )
            if connection is None:
                conn.commit()

    def get_due_flashcards(self, student_id: str, deck_id: Optional[str] = None) -> List[dict]:
        import json

        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            query = """
                SELECT card_id, topic_id, deck_id, front_text, back_text, interval_days, repetition_count, ease_factor, next_review_at, tags, provenance_json, stability, difficulty, last_review_at
                FROM flashcards WHERE student_id = :sid AND next_review_at <= :now
            """
            params = {"sid": student_id, "now": time.time()}
            if deck_id:
                query += " AND deck_id = :did"
                params["did"] = deck_id

            rows = conn.execute(text(query), params).fetchall()
            cards = []
            for r in rows:
                cards.append(
                    {
                        "card_id": r[0],
                        "topic_id": r[1],
                        "deck_id": r[2],
                        "front_text": r[3],
                        "back_text": r[4],
                        "interval_days": r[5],
                        "repetition_count": r[6],
                        "ease_factor": r[7],
                        "next_review_at": r[8],
                        "tags": json.loads(r[9]) if r[9] else [],
                        "provenance": json.loads(r[10]) if r[10] else None,
                        "stability": r[11],
                        "difficulty": r[12],
                        "last_review_at": r[13],
                    }
                )
            return cards

    def get_flashcard(self, card_id: str) -> Optional[dict]:
        import json

        from sqlalchemy import text

        with self.persister._engine.connect() as conn:
            r = conn.execute(
                text("""
                    SELECT card_id, student_id, topic_id, deck_id, front_text, back_text, interval_days, repetition_count, ease_factor, next_review_at, tags
                    FROM flashcards WHERE card_id = :cid
                """),
                {"cid": card_id},
            ).fetchone()
            if not r:
                return None
            return {
                "card_id": r[0],
                "student_id": r[1],
                "topic_id": r[2],
                "deck_id": r[3],
                "front_text": r[4],
                "back_text": r[5],
                "interval_days": r[6],
                "repetition_count": r[7],
                "ease_factor": r[8],
                "next_review_at": r[9],
                "tags": json.loads(r[10]) if r[10] else [],
            }

    def update_flashcard_review(
        self,
        card_id: str,
        interval: int,
        repetitions: int,
        stability: float,
        difficulty: float,
        reviewed_at: float,
        next_review: float,
        connection=None,
    ):
        from sqlalchemy import text

        with (
            nullcontext(connection) if connection is not None else self.persister._engine.connect()
        ) as conn:
            conn.execute(
                text("""
                    UPDATE flashcards 
                    SET interval_days = :interval, repetition_count = :rep_count, stability = :stability,
                        difficulty = :difficulty, last_review_at = :reviewed_at, next_review_at = :next_review
                    WHERE card_id = :cid
                """),
                {
                    "interval": interval,
                    "rep_count": repetitions,
                    "stability": stability,
                    "difficulty": difficulty,
                    "reviewed_at": reviewed_at,
                    "next_review": next_review,
                    "cid": card_id,
                },
            )
            if connection is None:
                conn.commit()
