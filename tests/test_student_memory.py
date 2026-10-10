import json
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

# Import local codebase modules
import sentio.config as config
from sentio.api.app import app
from sentio.session.session_manager import Session, SessionManager
from sentio.tutor.orchestrator import SentioOrchestrator
from tests.helpers import login_student


class TestSentioPhaseB(unittest.TestCase):
    """
    Test suite verifying the Phase B upgrades: Student Memory (B1),
    LangGraph Orchestrator (B2), and Observability Diagnostics (B3).
    """

    @classmethod
    def setUpClass(cls):
        # Enforce file-based SQL and Ollama backend configurations for testing
        config.nlp_cfg.LLM_BACKEND = "ollama"

    def setUp(self):
        # Clean up global agent and ensure it's not loaded
        from sentio.api.app import agent as global_agent

        global_agent.sm._sessions.clear()
        global_agent.sm._diagnostics.clear()
        global_agent._loaded = False

        # Delete old test DB if exists to guarantee a fresh database
        db_path = Path("data/test_tutor_sessions.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

        # Create fresh manager and load
        self.sm = SessionManager()
        self.sm.load()
        # Initialize orchestrator manually if needed
        self.orchestrator = SentioOrchestrator(global_agent)

    def tearDown(self):
        # Reset loaded agents
        from sentio.api.app import agent as global_agent

        global_agent.sm._sessions.clear()
        global_agent.sm._diagnostics.clear()
        global_agent._loaded = False

        # Clean up database file
        db_path = Path("test_tutor_sessions.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

    def test_student_profile_and_goals(self):
        """Verify student profiles can be created and learning goals are tracked."""
        student_id = "student_B1_test"

        # Ensure student exists
        self.sm.ensure_student_exists(student_id)

        # Add goals
        goal1_id = self.sm.add_learning_goal(
            student_id=student_id,
            goal_text="Understand Derivatives Chain Rule",
            topic_id="derivatives",
            target_date=time.time() + 86400,
        )
        goal2_id = self.sm.add_learning_goal(
            student_id=student_id, goal_text="Master limits definition", topic_id="limits"
        )

        self.assertIsNotNone(goal1_id)
        self.assertIsNotNone(goal2_id)

        # Fetch active goals
        active_goals = self.sm.get_learning_goals(student_id, status="active")
        self.assertEqual(len(active_goals), 2)
        goal_texts = [g["goal_text"] for g in active_goals]
        self.assertIn("Understand Derivatives Chain Rule", goal_texts)
        self.assertIn("Master limits definition", goal_texts)

    def test_dynamic_ema_topic_mastery(self):
        """Verify configurable EMA mastery progression and resistance to fluctuations."""
        student_id = "student_mastery_test"
        topic_id = "limits"

        # Initial status check
        self.sm.update_topic_mastery(student_id, topic_id, correct=True, difficulty="intermediate")

        # Fetch knowledge
        from sqlalchemy import text

        with self.sm.persister._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": student_id, "tid": topic_id},
            ).fetchone()

        initial_score = row[0]
        # With default alpha=0.25 and intermediate difficulty weight=1.0:
        # new_mastery = 0.0 + 0.25 * 1.0 * (1.0 - 0.0) = 0.25
        self.assertAlmostEqual(initial_score, 0.25, places=2)

        # Record another correct answer
        self.sm.update_topic_mastery(student_id, topic_id, correct=True, difficulty="intermediate")
        with self.sm.persister._engine.connect() as conn:
            row2 = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": student_id, "tid": topic_id},
            ).fetchone()
        second_score = row2[0]
        # new_mastery = 0.25 + 0.25 * 1.0 * (1.0 - 0.25) = 0.4375
        self.assertAlmostEqual(second_score, 0.4375, places=4)

        # Record a mistake to verify fluctuation resistance
        self.sm.update_topic_mastery(student_id, topic_id, correct=False, difficulty="intermediate")
        with self.sm.persister._engine.connect() as conn:
            row3 = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": student_id, "tid": topic_id},
            ).fetchone()
        third_score = row3[0]
        # new_mastery = 0.4375 + 0.25 * 1.0 * (0.0 - 0.4375) = 0.328125
        # Verification: A single mistake didn't drop it to 0.0, showing fluctuation resistance.
        self.assertAlmostEqual(third_score, 0.328125, places=5)

    def test_student_mistakes_tracking(self):
        """Verify that incorrect quiz answers are captured and summarized in mistake metrics."""
        student_id = "student_mistakes_test"
        session_id = "session_mock_1"

        # Ensure student exists
        self.sm.ensure_student_exists(student_id)

        # Create mock session
        session = Session(
            session_id=session_id,
            student_id=student_id,
            subject="mathematics",
            topic="derivatives",
            difficulty="beginner",
        )
        self.sm._sessions[session_id] = session

        # Record incorrect quiz attempts
        self.sm.record_quiz_attempt(
            session_id,
            correct=False,
            topic="derivatives",
            question_preview="Calculate derivative of x^2",
        )
        self.sm.record_quiz_attempt(
            session_id,
            correct=False,
            topic="derivatives",
            question_preview="Apply quotient rule to x/(x+1)",
        )
        self.sm.record_quiz_attempt(
            session_id, correct=True, topic="derivatives", question_preview="Derivative of sin(x)"
        )
        self.sm.record_quiz_attempt(
            session_id,
            correct=False,
            topic="limits",
            question_preview="Limit as x goes to infinity of 1/x",
        )

        # Retrieve mistake metrics
        metrics = self.sm.get_student_mistake_metrics(student_id)

        # Recent mistakes check (3 incorrect ones recorded)
        self.assertEqual(len(metrics["recent_mistakes_list"]), 3)
        self.assertEqual(metrics["recent_mistakes_list"][0]["topic"], "limits")
        self.assertEqual(metrics["recent_mistakes_list"][1]["topic"], "derivatives")

        # Recurring mistakes check (derivatives topic has count=2 > 1 wrong answers)
        recurring = metrics["recurring_mistakes"]
        self.assertEqual(len(recurring), 1)
        self.assertEqual(recurring[0]["topic"], "derivatives")
        self.assertEqual(recurring[0]["fail_count"], 2)

        # Mistake frequency check
        freq = metrics["mistake_frequency"]
        # derivatives: 2 incorrect, 1 correct => 3 total. Freq = 2/3 = 0.667
        self.assertAlmostEqual(freq["derivatives"]["frequency"], 0.667, places=3)
        self.assertEqual(freq["derivatives"]["attempts"], 3)

        # Test memory context formatting output
        context = self.sm.get_student_memory_context(student_id)
        self.assertIn("derivatives: 66.7% incorrect", context)
        self.assertIn("Topics with Recurring Struggles:", context)

    def test_langgraph_routing(self):
        """Verify the routing decisions based on student message content in Orchestrator."""
        # 1. Test message requiring research lookup
        state_research = self.orchestrator.route_after_memory(
            {
                "user_message": "Can you explain how derivatives represent slopes?",
                "retrieved_content": None,
            }
        )
        self.assertEqual(state_research, "research")

        # 2. Test standard message going straight to tutor node
        state_tutor = self.orchestrator.route_after_memory(
            {"user_message": "Okay, that makes sense. Thank you!", "retrieved_content": None}
        )
        self.assertEqual(state_tutor, "tutor")

        # 3. Test quiz request going to quiz stub node
        state_quiz = self.orchestrator.route_after_memory(
            {"user_message": "Can you test me with a quiz question?", "retrieved_content": None}
        )
        self.assertEqual(state_quiz, "quiz")

    def test_fastapi_diagnostics_and_memory_endpoints(self):
        """Verify FastAPI routes for goals, diagnostics, and memory return 200/201."""
        with TestClient(app) as client:
            student_id = login_student(client, admin=True)

            # 1. Create session
            resp_session = client.post(
                "/api/v1/sessions",
                json={
                    "student_id": student_id,
                    "subject": "mathematics",
                    "topic": "derivatives",
                    "difficulty": "beginner",
                },
            )
            self.assertEqual(resp_session.status_code, 201)
            session_id = resp_session.json()["session_id"]

            # 2. Add goal
            resp_goal = client.post(
                f"/api/v1/students/{student_id}/goals",
                json={"goal_text": "Complete Calculus 1 Basics", "topic_id": "derivatives"},
            )
            self.assertEqual(resp_goal.status_code, 201)
            self.assertTrue(resp_goal.json()["recorded"])

            # 3. List goals
            resp_list_goals = client.get(f"/api/v1/students/{student_id}/goals")
            self.assertEqual(resp_list_goals.status_code, 200)
            self.assertEqual(resp_list_goals.json()["count"], 1)
            self.assertEqual(
                resp_list_goals.json()["goals"][0]["goal_text"], "Complete Calculus 1 Basics"
            )

            # 4. Trigger chat to generate traces (triggers LLM backend mock/complete via patch)
            from unittest.mock import patch

            mock_response = json.dumps(
                {
                    "text": "Derivative is slope of the curve.",
                    "follow_up_question": "What is the limit definition?",
                    "encouragement": "You got this!",
                    "suggested_topic": "limits",
                }
            )
            with patch(
                "sentio.ai.nlp_engine.OllamaBackend.complete", return_value=(mock_response, 50)
            ):
                resp_chat = client.post(
                    f"/api/v1/sessions/{session_id}/chat",
                    json={
                        "message": "Explain the slope of a curve",
                        "quiz_correct": False,
                        "response_time_sec": 15.0,
                    },
                )
            self.assertEqual(resp_chat.status_code, 200)

            # 5. Fetch diagnostics
            resp_diagnostics = client.get(f"/api/v1/diagnostics/session/{session_id}")
            self.assertEqual(resp_diagnostics.status_code, 200)
            diag_data = resp_diagnostics.json()
            self.assertIn("traces", diag_data)
            self.assertIn("latest", diag_data)
            self.assertIn("selected_route", diag_data["latest"])
            self.assertIn("agent_timeline", diag_data["latest"])
            self.assertIn("memory_usage_kb", diag_data["latest"])

            # Route should have visited memory_lookup, research, and tutor
            route = diag_data["latest"]["selected_route"]
            self.assertIn("memory_lookup", route)
            self.assertIn("research", route)
            self.assertIn("tutor", route)

            # 6. Fetch student memory context
            resp_memory = client.get(f"/api/v1/students/{student_id}/memory")
            self.assertEqual(resp_memory.status_code, 200)
            mem_data = resp_memory.json()
            self.assertIn("formatted_memory_context", mem_data)
            self.assertIn("weak_topics", mem_data)
            self.assertIn("strong_topics", mem_data)


if __name__ == "__main__":
    unittest.main()
