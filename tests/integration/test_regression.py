import json
import unittest

from fastapi.testclient import TestClient

# Import local codebase modules
from sentio.ai.tutor_llm import NLPEngine, PromptBuilder, ResponseParser
from sentio.api.app import app
from sentio.rag.knowledge_base import KnowledgeBase
from sentio.session.manager import SessionManager, SessionStatus
from tests.helpers import login_student


class TestSentioRegression(unittest.TestCase):
    """
    Regression test suite to verify baseline functionality of
    the Sentio Emotion-Aware Tutor application.
    """

    def setUp(self):
        # Create fresh manager instances for each test
        self.sm = SessionManager()
        self.sm.load()

        self.kb = KnowledgeBase()
        self.kb.load()

        self.nlp = NLPEngine()
        # Initialize but don't fully load the Ollama connection to keep tests fast
        self.nlp.prompt_builder = PromptBuilder()
        self.nlp.parser = ResponseParser()

    def tearDown(self):
        # Clean up global agent state to prevent session leak across TestClient instances
        from sentio.api.app import agent

        agent.sm._sessions.clear()
        agent._loaded = False

    def test_database_session_persistence(self):
        """Verify that session creation, updating, and saving works in SQLite."""
        session = self.sm.create_session(
            student_id="test_student",
            subject="mathematics",
            topic="derivatives",
            difficulty="beginner",
        )
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.status, SessionStatus.ACTIVE)

        # Record a dummy exchange
        self.sm.record_exchange(session.session_id, tokens=150, latency_ms=450.0)
        self.assertEqual(session.total_exchanges, 1)
        self.assertEqual(session.total_tokens, 150)

        # Close session and verify analytics are produced and database entry updated
        analytics = self.sm.close_session(session.session_id)
        self.assertEqual(session.status, SessionStatus.CLOSED)
        self.assertEqual(analytics.total_exchanges, 1)
        self.assertEqual(analytics.total_tokens_used, 150)

        # Reload from persistence layer to check durability
        data = self.sm.persister.load_session_data(session.session_id)
        self.assertIsNotNone(data)
        self.assertEqual(data["student_id"], "test_student")
        self.assertEqual(data["total_exchanges"], 1)

    def test_retrieval_without_notes_refuses_instead_of_inventing_content(self):
        """Without selected notes, retrieval reports no source so the tutor refuses."""
        content = self.kb.retrieve(
            subject="My notes",
            topic="derivatives",
            difficulty="beginner",
            learning_state="neutral",
        )
        self.assertFalse(content.has_content())
        self.assertEqual(content.evidence_outcome, "no_source")

    def test_prompt_building_and_parsing(self):
        """Verify prompt templates and LLM response parsing logic."""
        builder = self.nlp.prompt_builder
        system_prompt = builder.build_system_prompt(
            subject="computer_science",
            topic="recursion",
            difficulty="beginner",
            learning_state="struggling",
            strategy="simplify",
            tone_instruction="Use simple analogies",
        )
        self.assertIn("computer_science", system_prompt.lower())
        self.assertIn("recursion", system_prompt.lower())
        self.assertIn("STRUGGLING", system_prompt.upper())
        self.assertIn("SIMPLIFY", system_prompt.upper())

        # Test parser behavior under correct JSON structure
        mock_response_json = json.dumps(
            {
                "text": "Recursion is like nesting dolls.",
                "follow_up_question": "What is the base case?",
                "encouragement": "Keep going!",
                "suggested_topic": "stack overflow",
            }
        )
        parsed = self.nlp.parser.parse(
            mock_response_json, "simplify", "struggling", 80, 200.0, "mock"
        )
        self.assertEqual(parsed.text, "Recursion is like nesting dolls.")
        self.assertEqual(parsed.follow_up_question, "What is the base case?")
        self.assertEqual(parsed.encouragement, "Keep going!")

        # Test parser robust handling under broken/text-only response
        mock_broken_response = "Here is the raw text not in JSON format"
        parsed_broken = self.nlp.parser.parse(
            mock_broken_response, "simplify", "struggling", 20, 100.0, "mock"
        )
        self.assertEqual(parsed_broken.text, mock_broken_response)

    def test_fastapi_http_endpoints(self):
        """Verify core FastAPI router endpoints respond correctly using TestClient."""
        with TestClient(app) as client:
            login_student(client, admin=True)
            # Health endpoint check
            resp_health = client.get("/api/v1/health")
            self.assertEqual(resp_health.status_code, 200)
            self.assertIn("status", resp_health.json())

            # The fixed subject list is gone: sessions take any label
            self.assertEqual(client.get("/api/v1/subjects").status_code, 404)

            # Create session endpoint check
            resp_session = client.post(
                "/api/v1/sessions",
                json={
                    "student_id": "api_test_student",
                    "subject": "physics",
                    "topic": "newtons_laws",
                    "difficulty": "beginner",
                },
            )
            self.assertEqual(resp_session.status_code, 201)
            session_id = resp_session.json()["session_id"]

            # Get session check
            resp_get = client.get(f"/api/v1/sessions/{session_id}")
            self.assertEqual(resp_get.status_code, 200)
            self.assertEqual(resp_get.json()["topic"], "newtons_laws")

    def test_rate_limiter_middleware(self):
        """Verify that the rate limiter middleware returns 429 after exceeding limit."""
        with TestClient(app) as client:
            login_student(client, admin=True)
            from unittest.mock import patch

            with patch("sentio.shared.rate_limit.RateLimiter.allow", return_value=False):
                resp = client.post(
                    "/api/v1/sessions",
                    json={
                        "student_id": "test_limit",
                        "subject": "physics",
                        "topic": "newtons_laws",
                        "difficulty": "beginner",
                    },
                )
                self.assertEqual(resp.status_code, 429)
                self.assertEqual(resp.json()["detail"], "Too many requests. Retry shortly.")

    def test_qdrant_vector_db(self):
        """Verify Qdrant client connection, collection creation, indexing, and search."""
        import uuid

        from sentio.rag.vector_db import QdrantVectorDB

        db = QdrantVectorDB()
        self.assertTrue(db.connect())
        self.assertTrue(db.create_collection_if_not_exists(vector_size=384))

        # Test trial index with 384-dim vector
        chk_id = str(uuid.uuid4())
        vec_384 = [0.1] * 384
        success = db.index_chunks(
            ids=[chk_id],
            vectors=[vec_384],
            payloads=[{"text": "Test RAG chunk", "subject": "math"}],
        )
        self.assertTrue(success)

        # Test trial search
        results = db.search(query_vector=vec_384, limit=1, filter_payload={"subject": "math"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], chk_id)
        self.assertEqual(results[0]["payload"]["text"], "Test RAG chunk")


if __name__ == "__main__":
    unittest.main()
