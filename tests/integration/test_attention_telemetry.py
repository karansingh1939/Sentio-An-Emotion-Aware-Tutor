"""
test_phase_e_final.py -- Integration and E2E Test Suite for Phase E Final Deliverables (E6C, E7, E8)
=================================================================================================
This test suite verifies:
  1. Telemetry API endpoint payload validation, content-length restrictions, and base64/image blocking.
  2. Telemetry database persistence, helper methods, indexes, and session isolation.
  3. Telemetry summaries calculation (attention score, focus rate, eye openness averages, recent state).
  4. Memory lookup integration and formatting.
  5. Feature-flagged adaptive tutoring rules (directives ON, default behavior OFF).
  6. Privacy controls validation (no raw media storage, media track release behavior on client, and DB cleanup).
"""

import unittest
from pathlib import Path
from unittest.mock import patch

# Configure test database and backend before importing the app
import sentio.config as config
from tests.helpers import login_student

config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = False

# Mock system_health_check to prevent webcam lock during testing
with patch(
    "sentio.shared.utils.system_health_check",
    return_value={"webcam_available": True, "emotion_model_ok": True},
):
    from fastapi.testclient import TestClient

    from sentio.api.app import agent, app
    from sentio.tutor.orchestrator import OrchestratorState, SentioOrchestrator


class TestPhaseEFinal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db_path = Path("data/test_phase_e_final.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

    def setUp(self):
        # Clear out session manager caches
        agent.sm._sessions.clear()
        agent.sm._diagnostics.clear()
        agent._loaded = False

        # Load agent and create DB structures
        agent.load()

        self.client = TestClient(app)
        self.student_id = login_student(self.client)
        enabled = patch.object(config.emotion_cfg, "ENABLED", True)
        enabled.start()
        self.addCleanup(enabled.stop)
        consent = self.client.post(
            f"/api/v1/student/{self.student_id}/consent",
            json={"consent_version": "camera-v1", "preferences": {"telemetry": True}},
        )
        self.assertEqual(consent.status_code, 200)

        # Create a test session
        res = self.client.post(
            "/api/v1/sessions",
            json={
                "student_id": self.student_id,
                "subject": "physics",
                "topic": "mechanics",
                "difficulty": "intermediate",
            },
        )
        self.assertEqual(res.status_code, 201)
        self.session_id = res.json()["session_id"]

    def tearDown(self):
        # Clean up database records and sessions
        if self.session_id:
            try:
                self.client.delete(f"/api/v1/sessions/{self.session_id}")
            except Exception:
                pass
        agent.shutdown()

        db_path = Path("test_phase_e_final.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

    # ── 1. TELEMETRY VALIDATION ───────────────────────────────────────────

    def test_telemetry_validation_valid(self):
        """Verify that a valid telemetry payload is accepted successfully."""
        payload = {
            "attention_score": 0.85,
            "focused": 1,
            "eye_openness": 0.78,
            "head_pose_pitch": 5.2,
            "head_pose_yaw": -10.4,
            "emotion": "focused",
        }
        res = self.client.post(f"/api/v1/sessions/{self.session_id}/telemetry", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Telemetry accepted", res.json()["message"])

    def test_telemetry_validation_invalid_bounds(self):
        """Verify that out-of-bounds metrics are rejected (e.g. attention > 1.0)."""
        payload = {
            "attention_score": 1.5,  # Invalid
            "focused": 1,
            "eye_openness": 0.8,
            "head_pose_pitch": 0.0,
            "head_pose_yaw": 0.0,
            "emotion": "focused",
        }
        res = self.client.post(f"/api/v1/sessions/{self.session_id}/telemetry", json=payload)
        self.assertEqual(res.status_code, 422)  # Pydantic validation error

    def test_telemetry_validation_oversized(self):
        """Verify that oversized payloads (>1000 bytes) are rejected with HTTP 413."""
        # Create a payload that is extremely large (> 1000 bytes)
        large_emotion = "focused" * 150
        payload = {
            "attention_score": 0.9,
            "focused": 1,
            "eye_openness": 0.9,
            "head_pose_pitch": 0.0,
            "head_pose_yaw": 0.0,
            "emotion": large_emotion,
        }
        res = self.client.post(f"/api/v1/sessions/{self.session_id}/telemetry", json=payload)
        self.assertEqual(res.status_code, 413)

    def test_telemetry_validation_raw_image_block(self):
        """Verify that payloads containing potential base64/image tags are blocked."""
        payload = {
            "attention_score": 0.9,
            "focused": 1,
            "eye_openness": 0.9,
            "head_pose_pitch": 0.0,
            "head_pose_yaw": 0.0,
            "emotion": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA",
        }
        res = self.client.post(f"/api/v1/sessions/{self.session_id}/telemetry", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid telemetry payload contents", res.json()["detail"])

    # ── 2. DATABASE PERSISTENCE & SESSION ISOLATION ───────────────────────

    def test_telemetry_persistence_and_isolation(self):
        """Verify that telemetry is saved to DB, retrievable, and isolated by session."""
        # Log telemetry to first session
        agent.sm.save_attention_log(self.session_id, 0.9, 1, 0.85, 1.2, -2.1, "focused")
        agent.sm.save_attention_log(self.session_id, 0.4, 0, 0.15, 12.0, 15.2, "distracted")

        # Verify first session telemetry was persisted
        logs1 = agent.sm.get_attention_logs(self.session_id)
        self.assertEqual(len(logs1), 2)
        self.assertEqual(logs1[0]["emotion"], "focused")
        self.assertEqual(logs1[1]["emotion"], "distracted")

        # Create second session
        res = self.client.post(
            "/api/v1/sessions",
            json={
                "student_id": "other_student",
                "subject": "physics",
                "topic": "mechanics",
                "difficulty": "intermediate",
            },
        )
        self.assertEqual(res.status_code, 201)
        session_id_2 = res.json()["session_id"]

        try:
            # Verify second session starts with no telemetry logs
            logs2 = agent.sm.get_attention_logs(session_id_2)
            self.assertEqual(len(logs2), 0)

            # Log to second session and check isolation
            agent.sm.save_attention_log(session_id_2, 0.7, 1, 0.75, 0.5, 0.5, "focused")
            self.assertEqual(len(agent.sm.get_attention_logs(self.session_id)), 2)
            self.assertEqual(len(agent.sm.get_attention_logs(session_id_2)), 1)
        finally:
            self.client.delete(f"/api/v1/sessions/{session_id_2}")

    # ── 3. TELEMETRY SUMMARIES ────────────────────────────────────────────

    def test_telemetry_summaries_calculation(self):
        """Verify metrics calculations (avg_attention, focus_rate, recent_state)."""
        # Save a sequence of telemetry points
        # 3 points: 2 focused, 1 distracted. Averages:
        # attention = (0.9 + 0.3 + 0.6) / 3 = 0.60
        # focus_rate = (1 + 0 + 1) / 3 = 0.667
        # eye_openness = (0.8 + 0.2 + 0.5) / 3 = 0.50
        # pitch = (2.0 + 8.0 + 5.0) / 3 = 5.0
        # yaw = (-4.0 + 10.0 + 3.0) / 3 = 3.0
        agent.sm.save_attention_log(self.session_id, 0.9, 1, 0.8, 2.0, -4.0, "focused")
        agent.sm.save_attention_log(self.session_id, 0.3, 0, 0.2, 8.0, 10.0, "distracted")
        agent.sm.save_attention_log(self.session_id, 0.6, 1, 0.5, 5.0, 3.0, "low_engagement")

        summary = agent.sm.get_attention_summary(self.session_id)
        self.assertEqual(summary["count"], 3)
        self.assertAlmostEqual(summary["avg_attention"], 0.60, places=2)
        self.assertAlmostEqual(summary["focus_rate"], 2 / 3, places=2)
        self.assertAlmostEqual(summary["avg_eye_openness"], 0.50, places=2)
        self.assertAlmostEqual(summary["avg_pitch"], 5.0, places=1)
        self.assertAlmostEqual(summary["avg_yaw"], 3.0, places=1)
        self.assertEqual(summary["recent_state"], "low_engagement")

    # ── 4 & 5. MEMORY LOOKUP & FEATURE FLAGS (ADAPTIVE TUTORING ON/OFF) ───

    def test_memory_lookup_integration_flag_off(self):
        """Verify memory lookup nodes inject summaries but NO directives when flag is OFF."""
        # 1. Save telemetry
        agent.sm.save_attention_log(self.session_id, 0.9, 1, 0.8, 0.0, 0.0, "focused")

        # 2. Setup state
        orchestrator = SentioOrchestrator(agent)
        state: OrchestratorState = {
            "student_id": self.student_id,
            "session_id": self.session_id,
            "strategy": "standard",
            "learning_state": "neutral",
            "user_message": "Explain forces",
            "subject": "physics",
            "topic": "mechanics",
            "difficulty": "intermediate",
            "student_memory": "",
            "search_query": "",
            "search_results": [],
            "tutor_response": None,
            "timeline": [],
            "route": [],
        }

        # 3. Ensure Flag is OFF
        config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = False

        # 4. Run memory lookup
        output_state = orchestrator.memory_lookup_node(state)
        student_memory = output_state["student_memory"]

        # Summary must exist but no behavioral directives
        self.assertIn("Student attention summary", student_memory)
        self.assertIn("Focus rate 100%", student_memory)
        self.assertNotIn("INSTRUCTION (Student is FOCUSED)", student_memory)
        self.assertNotIn("shorter explanations", student_memory)

    def test_memory_lookup_integration_flag_on_focused(self):
        """Verify memory lookup node appends FOCUSED directives when flag is ON."""
        agent.sm.save_attention_log(self.session_id, 0.9, 1, 0.8, 0.0, 0.0, "focused")

        orchestrator = SentioOrchestrator(agent)
        state: OrchestratorState = {
            "student_id": self.student_id,
            "session_id": self.session_id,
            "strategy": "standard",
            "learning_state": "neutral",
            "user_message": "Explain forces",
            "subject": "physics",
            "topic": "mechanics",
            "difficulty": "intermediate",
            "student_memory": "",
            "search_query": "",
            "search_results": [],
            "tutor_response": None,
            "timeline": [],
            "route": [],
        }

        # Enable flag
        config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = True

        try:
            output_state = orchestrator.memory_lookup_node(state)
            student_memory = output_state["student_memory"]

            self.assertIn("Student attention summary", student_memory)
            self.assertIn("INSTRUCTION (Student is FOCUSED)", student_memory)
            self.assertIn("normal tutoring pacing", student_memory)
        finally:
            config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = False

    def test_memory_lookup_integration_flag_on_distracted(self):
        """Verify memory lookup node appends DISTRACTED directives when flag is ON."""
        # Set focus rate low: 1 focused, 2 distracted (focus_rate = 0.33 < 0.50)
        agent.sm.save_attention_log(self.session_id, 0.8, 1, 0.8, 0.0, 0.0, "focused")
        agent.sm.save_attention_log(self.session_id, 0.2, 0, 0.8, 0.0, 0.0, "distracted")
        agent.sm.save_attention_log(self.session_id, 0.3, 0, 0.8, 0.0, 0.0, "distracted")

        orchestrator = SentioOrchestrator(agent)
        state: OrchestratorState = {
            "student_id": self.student_id,
            "session_id": self.session_id,
            "strategy": "standard",
            "learning_state": "neutral",
            "user_message": "Explain forces",
            "subject": "physics",
            "topic": "mechanics",
            "difficulty": "intermediate",
            "student_memory": "",
            "search_query": "",
            "search_results": [],
            "tutor_response": None,
            "timeline": [],
            "route": [],
        }

        config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = True

        try:
            output_state = orchestrator.memory_lookup_node(state)
            student_memory = output_state["student_memory"]

            self.assertIn("INSTRUCTION (Student is DISTRACTED)", student_memory)
            self.assertIn("shorter explanations", student_memory)
            self.assertIn("simpler, more direct wording", student_memory)
        finally:
            config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = False

    def test_memory_lookup_integration_flag_on_low_engagement(self):
        """Verify memory lookup node appends LOW_ENGAGEMENT directives when flag is ON."""
        # Set average attention low: 3 points all focused but low attention (avg_attention = 0.55 < 0.65)
        agent.sm.save_attention_log(self.session_id, 0.5, 1, 0.8, 0.0, 0.0, "focused")
        agent.sm.save_attention_log(self.session_id, 0.6, 1, 0.8, 0.0, 0.0, "focused")
        agent.sm.save_attention_log(self.session_id, 0.55, 1, 0.8, 0.0, 0.0, "focused")

        orchestrator = SentioOrchestrator(agent)
        state: OrchestratorState = {
            "student_id": self.student_id,
            "session_id": self.session_id,
            "strategy": "standard",
            "learning_state": "neutral",
            "user_message": "Explain forces",
            "subject": "physics",
            "topic": "mechanics",
            "difficulty": "intermediate",
            "student_memory": "",
            "search_query": "",
            "search_results": [],
            "tutor_response": None,
            "timeline": [],
            "route": [],
        }

        config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = True

        try:
            output_state = orchestrator.memory_lookup_node(state)
            student_memory = output_state["student_memory"]

            self.assertIn("INSTRUCTION (Student has LOW ENGAGEMENT)", student_memory)
            self.assertIn("smaller, bite-sized chunks", student_memory)
            self.assertIn("Encourage active student interaction", student_memory)
            self.assertIn("Suggest reviewing flashcard decks", student_memory)
        finally:
            config.tutor_cfg.ENABLE_ADAPTIVE_TUTORING = False

    # ── 6. PRIVACY & CLEANUP BEHAVIOR ─────────────────────────────────────

    def test_privacy_control_storage_and_cleanup(self):
        """Verify database contains no raw media and session deletion clears telemetry."""
        # Log telemetry
        agent.sm.save_attention_log(self.session_id, 0.95, 1, 0.88, 1.1, -1.5, "focused")

        # Verify no frames or base64 exists in telemetry DB rows
        logs = agent.sm.get_attention_logs(self.session_id)
        self.assertEqual(len(logs), 1)

        log_entry = logs[0]
        # Only simple metrics stored
        self.assertEqual(log_entry["attention_score"], 0.95)
        self.assertEqual(log_entry["focused"], 1)
        self.assertEqual(log_entry["eye_openness"], 0.88)
        self.assertEqual(log_entry["head_pose_pitch"], 1.1)
        self.assertEqual(log_entry["head_pose_yaw"], -1.5)
        self.assertEqual(log_entry["emotion"], "focused")

        # Verify no image field exists (privacy requirement)
        self.assertNotIn("frame", log_entry)
        self.assertNotIn("image", log_entry)
        self.assertNotIn("raw_media", log_entry)

        # Delete session
        sid_to_check = self.session_id
        res = self.client.delete(f"/api/v1/sessions/{self.session_id}")
        self.assertEqual(res.status_code, 200)
        self.session_id = None  # Prevent double delete in tearDown

        # Check that telemetry was cleared from DB (cleanup behavior)
        with agent.sm.persister._engine.connect() as conn:
            from sqlalchemy import text

            rows = conn.execute(
                text("SELECT id FROM attention_logs WHERE session_id = :sid"), {"sid": sid_to_check}
            ).fetchall()
            self.assertEqual(len(rows), 0)

    def test_cleanup_already_closed_session(self):
        """Verify closing an already closed session does not throw errors and remains clean."""
        sid = self.session_id
        res = self.client.delete(f"/api/v1/sessions/{sid}")
        self.assertEqual(res.status_code, 200)
        self.session_id = None  # Prevent double delete in tearDown

        # Close again (using session_manager directly as API might return 404 since it's removed from active sessions)
        try:
            agent.sm.close_session(sid)
        except Exception as e:
            self.fail(f"close_session raised an exception on pre-closed session: {e}")

        # Repeated cleanup call
        try:
            agent.sm.clear_session_telemetry(sid)
        except Exception as e:
            self.fail(f"clear_session_telemetry raised an exception when called repeatedly: {e}")

    def test_cleanup_session_with_no_telemetry(self):
        """Verify closing a session with no telemetry logs completes successfully."""
        sid = self.session_id
        res = self.client.delete(f"/api/v1/sessions/{sid}")
        self.assertEqual(res.status_code, 200)
        self.session_id = None

        with agent.sm.persister._engine.connect() as conn:
            from sqlalchemy import text

            rows = conn.execute(
                text("SELECT id FROM attention_logs WHERE session_id = :sid"), {"sid": sid}
            ).fetchall()
            self.assertEqual(len(rows), 0)

    def test_cleanup_session_with_multiple_telemetry_records(self):
        """Verify database is clean when closing a session with multiple telemetry records."""
        agent.sm.save_attention_log(self.session_id, 0.9, 1, 0.8, 0.0, 0.0, "focused")
        agent.sm.save_attention_log(self.session_id, 0.7, 1, 0.75, 1.0, 1.0, "focused")
        agent.sm.save_attention_log(self.session_id, 0.3, 0, 0.6, 10.0, -10.0, "distracted")

        logs = agent.sm.get_attention_logs(self.session_id)
        self.assertEqual(len(logs), 3)

        sid = self.session_id
        res = self.client.delete(f"/api/v1/sessions/{sid}")
        self.assertEqual(res.status_code, 200)
        self.session_id = None

        with agent.sm.persister._engine.connect() as conn:
            from sqlalchemy import text

            rows = conn.execute(
                text("SELECT id FROM attention_logs WHERE session_id = :sid"), {"sid": sid}
            ).fetchall()
            self.assertEqual(len(rows), 0)

    def test_cleanup_graceful_error_handling(self):
        """Verify session closing completes even if database query fails during telemetry deletion."""
        original_connect = agent.sm.persister._engine.connect

        def mock_connect():
            conn = original_connect()
            original_execute = conn.execute

            def mock_execute(statement, *args, **kwargs):
                if "DELETE FROM attention_logs" in str(statement):
                    raise RuntimeError("Mocked database connection failure during delete")
                return original_execute(statement, *args, **kwargs)

            conn.execute = mock_execute
            return conn

        agent.sm.persister._engine.connect = mock_connect
        try:
            res = self.client.delete(f"/api/v1/sessions/{self.session_id}")
            self.assertEqual(res.status_code, 200)
            self.session_id = None
        finally:
            agent.sm.persister._engine.connect = original_connect


if __name__ == "__main__":
    unittest.main()
