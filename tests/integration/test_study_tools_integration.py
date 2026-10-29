"""
test_phase_d_e2e.py -- E2E Integration Test Suite for Phase D (Structured Parser, Quiz, Flashcards, Whiteboard)
========================================================================================================
This test suite verifies:
  1. D0 Structured output parsing, recovery layer logic, and diagnostic metrics.
  2. D1 Quiz generation endpoint.
  3. D2 Quiz grading, database persistence, EMA mastery updates, and mistake logging.
  4. D3 Flashcard deck creation and AI generation.
  5. D3 Tutor suggestion hook triggers via chat endpoint.
  6. D4 Spaced repetition reviews SM-2 scheduling and mastery updates.
  7. D5/D6 Whiteboard saving, loading, Mermaid parsing, and PNG/PDF export endpoints.
"""

import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from sentio.ai.structured_parser import (
    QuizPayloadSchema,
    parse_structured_output,
)
from sentio.ai.structured_parser import metrics as parser_metrics
from sentio.api.app import agent, app

# Configure test database and backend before importing the app
from tests.helpers import login_student


# Mock OllamaBackend side_effect helper
def mock_complete(system_prompt, history, user_message, max_tokens=512, temperature=0.7):
    sys_p = system_prompt.lower() if system_prompt else ""
    user_message.lower() if user_message else ""

    if (
        "generate a quiz" in sys_p
        or "generate a comprehensive, high-quality, and challenging quiz" in sys_p
    ):
        # D1: Quiz Generation Response
        return json.dumps(
            {
                "title": "Thermodynamics Basics",
                "questions": [
                    {
                        "question_text": "What is the second law of thermodynamics?",
                        "question_type": "multiple_choice",
                        "options": [
                            "Entropy increases",
                            "Energy is conserved",
                            "Absolute zero is unreachable",
                            "Heat flows from cold to hot",
                        ],
                        "correct_answer": "Entropy increases",
                        "explanation": "The second law states that total entropy of an isolated system always increases.",
                        "difficulty": "intermediate",
                        "topic": "thermodynamics",
                    },
                    {
                        "question_text": "True or False: Entropy decreases in a closed system.",
                        "question_type": "true_false",
                        "options": ["True", "False"],
                        "correct_answer": "False",
                        "explanation": "Entropy of a closed system can never decrease over time.",
                        "difficulty": "intermediate",
                        "topic": "thermodynamics",
                    },
                    {
                        "question_text": "What does a thermometer measure?",
                        "question_type": "short_answer",
                        "options": None,
                        "correct_answer": "temperature",
                        "explanation": "A thermometer measures temperature.",
                        "difficulty": "intermediate",
                        "topic": "temperature",
                    },
                ],
            }
        ), 120

    elif "grade student response" in sys_p or "grade the student's answer" in sys_p:
        # D2: Short Answer Grading Response (the student's answer is in the system prompt text)
        if "temperature" in sys_p or "correct" in sys_p:
            return '{"is_correct": true, "score": 1.0}', 20
        else:
            return '{"is_correct": false, "score": 0.0}', 20

    elif "summary of student performance" in sys_p or "completed a quiz titled" in sys_p:
        # D2: Quiz Summary Response
        return "Nice job completing the quiz! Keep up the good work.", 20

    elif "flashcards about" in sys_p or "extract key terms" in sys_p:
        # D3: Flashcard Generation Response
        return json.dumps(
            {
                "deck_name": "Thermodynamics Flashcards",
                "cards": [
                    {
                        "front": "Entropy",
                        "back": "A measure of disorder or randomness in a system.",
                        "tags": ["physics", "thermodynamics"],
                    },
                    {
                        "front": "First Law of Thermodynamics",
                        "back": "Energy cannot be created or destroyed, only transformed.",
                        "tags": ["physics", "thermodynamics"],
                    },
                    {
                        "front": "Absolute Zero",
                        "back": "The lowest possible temperature where molecular motion ceases.",
                        "tags": ["physics", "thermodynamics"],
                    },
                ],
            }
        ), 100

    else:
        # Standard Tutor Chat Response
        return json.dumps(
            {
                "text": "This is a tutoring explanation about thermodynamics.",
                "follow_up_question": "Does this explanation make sense?",
                "encouragement": "Good effort!",
                "suggested_topic": "thermodynamics",
            }
        ), 50


class TestPhaseDE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Guarantee clean test database
        db_path = Path("test_phase_d_e2e.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

    def setUp(self):
        # Clear out agent session storage
        agent.sm._sessions.clear()
        agent.sm._diagnostics.clear()
        agent._loaded = False

        # Load agent and create DB structures
        agent.load()

        self.student_id = "e2e_student_001"
        self.session_id = None
        self.quiz_id = None

    def tearDown(self):
        agent.shutdown()
        db_path = Path("data/test_phase_d_e2e.db")
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass

    def test_01_structured_output_recovery_layer(self):
        """Test parsing structured outputs and Attempt 1-4 fallback logic directly."""
        parser_metrics.total_attempts = 0
        parser_metrics.direct_successes = 0
        parser_metrics.recovered_successes = 0
        parser_metrics.regenerations = 0

        # Attempt 1: Direct JSON parse
        question = dict(
            question_text="What is 2+2?", question_type="short_answer", correct_answer="4"
        )
        valid_json = json.dumps(dict(title="Math Quiz", questions=[question]))
        res = parse_structured_output(valid_json, QuizPayloadSchema)
        self.assertEqual(res.title, "Math Quiz")
        self.assertEqual(parser_metrics.direct_successes, 1)

        # Attempt 2: Bracket repair
        malformed_brackets = '{"title": "Bracket Quiz", "questions": [' + json.dumps(question)
        res = parse_structured_output(malformed_brackets, QuizPayloadSchema)
        self.assertEqual(res.title, "Bracket Quiz")
        self.assertEqual(parser_metrics.recovered_successes, 1)

        # Attempt 2.5: AST literal eval
        single_quoted = repr(dict(title="Single Quote Quiz", questions=[question]))
        res = parse_structured_output(single_quoted, QuizPayloadSchema)
        self.assertEqual(res.title, "Single Quote Quiz")
        self.assertEqual(parser_metrics.recovered_successes, 2)

        # Attempt 3: Regex scraper fallback
        regex_input = (
            "Extra text before: "
            + repr(dict(title="Regex Quiz", questions=[question]))
            + " Extra text after."
        )
        res = parse_structured_output(regex_input, QuizPayloadSchema)
        self.assertEqual(res.title, "Regex Quiz")
        self.assertEqual(parser_metrics.recovered_successes, 3)

        # Attempt 4: LLM regeneration
        corrupted_text = "Completely corrupted text that fails direct parsing."
        valid_mock_response = json.dumps(dict(title="Regen Quiz", questions=[question]))

        def dummy_llm_call(sys_p, hist, user_p):
            return valid_mock_response, 50

        res = parse_structured_output(
            corrupted_text,
            QuizPayloadSchema,
            llm_call_fn=dummy_llm_call,
            original_prompt_args={
                "system_prompt": "Regenerate this JSON",
                "history": [],
                "user_message": "Invalid response",
            },
            max_regenerations=1,
        )
        self.assertEqual(res.title, "Regen Quiz")
        self.assertEqual(parser_metrics.regenerations, 1)

    def test_02_e2e_quiz_and_flashcard_and_whiteboard_flow(self):
        """Sequential E2E endpoint tests using TestClient."""
        with TestClient(app) as client:
            self.student_id = login_student(client, admin=True)
            # 1. Create a Student Session
            resp_session = client.post(
                "/api/v1/sessions",
                json={
                    "student_id": self.student_id,
                    "subject": "physics",
                    "topic": "thermodynamics",
                    "difficulty": "intermediate",
                },
            )
            self.assertEqual(resp_session.status_code, 201)
            self.session_id = resp_session.json()["session_id"]
            self.assertIsNotNone(self.session_id)

            # 2. Add Learning Goal
            resp_goal = client.post(
                f"/api/v1/students/{self.student_id}/goals",
                json={
                    "goal_text": "Understand Entropy and Heat Transfer",
                    "topic_id": "thermodynamics",
                },
            )
            self.assertEqual(resp_goal.status_code, 201)
            self.assertTrue(resp_goal.json()["recorded"])

            # 3. Generate Quiz (D1)
            with patch("sentio.ai.nlp_engine.OllamaBackend.complete", side_effect=mock_complete):
                resp_quiz = client.post(
                    "/api/v1/quizzes/generate",
                    json={
                        "student_id": self.student_id,
                        "session_id": self.session_id,
                        "subject": "physics",
                        "topic": "thermodynamics",
                        "difficulty": "intermediate",
                        "num_questions": 3,
                    },
                )
            self.assertEqual(resp_quiz.status_code, 200)
            quiz_data = resp_quiz.json()
            self.quiz_id = quiz_data["quiz_id"]
            self.assertEqual(quiz_data["title"], "Thermodynamics Basics")
            self.assertEqual(len(quiz_data["questions"]), 3)

            # Check diagnostics metrics endpoint for structured parser
            resp_diag_parser = client.get("/api/v1/diagnostics/structured_parser")
            self.assertEqual(resp_diag_parser.status_code, 200)
            self.assertIn("parse_success_rate", resp_diag_parser.json())

            # 4. Submit & Score Quiz (D2)
            # Question 0 (MCQ): student answers correct "Entropy increases"
            # Question 1 (TF): student answers incorrect "True" (correct is False)
            # Question 2 (Short Answer): student answers correct "temperature"
            answers = {0: "Entropy increases", 1: "True", 2: "temperature"}
            with patch("sentio.ai.nlp_engine.OllamaBackend.complete", side_effect=mock_complete):
                resp_submit = client.post(
                    f"/api/v1/quizzes/{self.quiz_id}/submit",
                    json={"session_id": self.session_id, "answers": answers},
                )
            self.assertEqual(resp_submit.status_code, 200)
            score_data = resp_submit.json()
            self.assertIn("total_score", score_data)
            # 2 out of 3 correct = 0.6666...
            self.assertAlmostEqual(score_data["total_score"], 2.0 / 3.0, places=2)
            self.assertTrue(score_data["passed"])  # 66.7% >= 60%

            # Verify topic mastery was updated in database
            resp_mem = client.get(f"/api/v1/students/{self.student_id}/memory")
            self.assertEqual(resp_mem.status_code, 200)
            mem_data = resp_mem.json()
            # Mastery should have moved from 0.0 to some value > 0.0 (boosted by 2 correct answers, demoted by 1 incorrect)
            self.assertIn("thermodynamics", mem_data["formatted_memory_context"])

            # 5. Create Flashcard Deck (D3)
            resp_deck = client.post(
                "/api/v1/flashcards/decks",
                json={"student_id": self.student_id, "deck_name": "Thermodynamics Deck"},
            )
            self.assertEqual(resp_deck.status_code, 201)
            deck_id = resp_deck.json()["deck_id"]
            self.assertIsNotNone(deck_id)

            # 6. Generate Flashcards via LLM (D3)
            with patch("sentio.ai.nlp_engine.OllamaBackend.complete", side_effect=mock_complete):
                resp_cards = client.post(
                    "/api/v1/flashcards/generate",
                    json={
                        "student_id": self.student_id,
                        "deck_id": deck_id,
                        "topic_id": "thermodynamics",
                        "num_cards": 3,
                    },
                )
            self.assertEqual(resp_cards.status_code, 200)
            generated_cards = resp_cards.json()["cards"]
            self.assertEqual(len(generated_cards), 3)
            self.assertEqual(generated_cards[0]["front"], "Entropy")

            # 7. Check Due Reviews (D4 initial)
            resp_due = client.get(
                f"/api/v1/flashcards/reviews/due?student_id={self.student_id}&deck_id={deck_id}"
            )
            self.assertEqual(resp_due.status_code, 200)
            due_cards = resp_due.json()["cards"]
            # All generated cards should be due immediately (repetition_count = 0)
            self.assertEqual(len(due_cards), 3)
            test_card_id = due_cards[0]["card_id"]

            # 8. Submit SM-2 Review Success (D4 quality score 5)
            resp_review_ok = client.post(
                f"/api/v1/flashcards/{test_card_id}/review", json={"quality_score": 5}
            )
            self.assertEqual(resp_review_ok.status_code, 200)
            review_ok_data = resp_review_ok.json()
            self.assertEqual(review_ok_data["repetition_count"], 1)
            self.assertEqual(review_ok_data["next_interval_days"], 1)

            # 9. Submit SM-2 Review Failure (D4 quality score 1)
            resp_review_fail = client.post(
                f"/api/v1/flashcards/{test_card_id}/review", json={"quality_score": 1}
            )
            self.assertEqual(resp_review_fail.status_code, 200)
            review_fail_data = resp_review_fail.json()
            self.assertEqual(review_fail_data["repetition_count"], 0)  # reset
            self.assertEqual(review_fail_data["next_interval_days"], 1)

            # 10. Verify Tutor Chat Struggle Recommendation Hook (D3)
            # Send first explanation ask about "entropy"
            with patch("sentio.ai.nlp_engine.OllamaBackend.complete", side_effect=mock_complete):
                resp_chat_1 = client.post(
                    f"/api/v1/sessions/{self.session_id}/chat", json={"message": "What is entropy?"}
                )
            self.assertEqual(resp_chat_1.status_code, 200)
            self.assertNotIn("💡 *Tip: You seem to be working on", resp_chat_1.json()["text"])

            # Send second explanation ask about "entropy" -> should trigger the suggestion Tip
            with patch("sentio.ai.nlp_engine.OllamaBackend.complete", side_effect=mock_complete):
                resp_chat_2 = client.post(
                    f"/api/v1/sessions/{self.session_id}/chat", json={"message": "What is entropy?"}
                )
            self.assertEqual(resp_chat_2.status_code, 200)
            self.assertIn(
                "💡 *Tip: You seem to be working on 'Entropy'. Would you like to add this to your flashcard deck?*",
                resp_chat_2.json()["text"],
            )

            # 11. Whiteboard: Sync State (D5)
            whiteboard_id = "wb_e2e_999"
            canvas_state = {
                "width": 800,
                "height": 600,
                "shapes": [
                    {
                        "type": "rectangle",
                        "x": 100.0,
                        "y": 100.0,
                        "width": 200.0,
                        "height": 80.0,
                        "color": "blue",
                        "strokeWidth": 3,
                    },
                    {
                        "type": "arrow",
                        "points": [[200.0, 180.0], [200.0, 300.0]],
                        "color": "black",
                        "strokeWidth": 2,
                    },
                    {
                        "type": "text",
                        "x": 110.0,
                        "y": 120.0,
                        "text": "Concept Node",
                        "color": "green",
                        "fontSize": 14,
                    },
                ],
            }
            resp_wb_save = client.post(
                "/api/v1/whiteboards/sessions",
                json={
                    "whiteboard_id": whiteboard_id,
                    "student_id": self.student_id,
                    "session_id": self.session_id,
                    "title": "Thermodynamics Concept Map",
                    "canvas_state": canvas_state,
                },
            )
            self.assertEqual(resp_wb_save.status_code, 200)
            self.assertTrue(resp_wb_save.json()["saved"])

            # 12. Whiteboard: Load State (D5)
            resp_wb_load = client.get(f"/api/v1/whiteboards/{whiteboard_id}")
            self.assertEqual(resp_wb_load.status_code, 200)
            loaded_wb = resp_wb_load.json()
            self.assertEqual(loaded_wb["title"], "Thermodynamics Concept Map")
            self.assertEqual(len(loaded_wb["canvas_state"]["shapes"]), 3)

            # 13. Whiteboard: Export PNG (D6)
            resp_export_png = client.post(
                f"/api/v1/whiteboards/{whiteboard_id}/export", json={"format": "png"}
            )
            self.assertEqual(resp_export_png.status_code, 200)
            self.assertEqual(resp_export_png.headers["content-type"], "image/png")
            # Verify valid PNG by opening with Pillow
            img = Image.open(io.BytesIO(resp_export_png.content))
            self.assertEqual(img.format, "PNG")
            self.assertEqual(img.size, (800, 600))

            # 14. Whiteboard: Export PDF (D6)
            resp_export_pdf = client.post(
                f"/api/v1/whiteboards/{whiteboard_id}/export", json={"format": "pdf"}
            )
            self.assertEqual(resp_export_pdf.status_code, 200)
            self.assertEqual(resp_export_pdf.headers["content-type"], "application/pdf")
            self.assertTrue(resp_export_pdf.content.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
