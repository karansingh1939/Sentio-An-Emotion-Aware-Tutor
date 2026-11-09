"""
test_structured_output.py -- Unit Tests for Structured Output Reliability Layer (Phase D0)
========================================================================================
Verifies:
  - Direct valid JSON parsing
  - Repair of missing brackets / truncated JSON
  - Repair of invalid single-quoted JSON
  - Graceful handling of missing fields (validation error)
  - Resilience to hallucinated extra fields
  - Graceful handling of empty responses
  - Mocked LLM regeneration / retry loop
"""

import unittest

from pydantic import ValidationError

from sentio.ai.structured_parser import (
    FlashcardPayloadSchema,
    QuizPayloadSchema,
    metrics,
    parse_structured_output,
)


class TestStructuredParser(unittest.TestCase):
    def setUp(self):
        # Reset metrics
        metrics.total_attempts = 0
        metrics.direct_successes = 0
        metrics.recovered_successes = 0
        metrics.regenerations = 0
        metrics.total_failures = 0

    def test_direct_valid_json(self):
        raw = """
        {
            "title": "Introduction to Physics",
            "questions": [
                {
                    "question_text": "What is the speed of light?",
                    "question_type": "multiple_choice",
                    "options": ["3e8 m/s", "1e8 m/s", "5e8 m/s"],
                    "correct_answer": "3e8 m/s",
                    "explanation": "Light travels at approximately 300,000 km/s in a vacuum.",
                    "difficulty": "beginner",
                    "topic": "physics_intro"
                }
            ]
        }
        """
        obj = parse_structured_output(raw, QuizPayloadSchema)
        self.assertEqual(obj.title, "Introduction to Physics")
        self.assertEqual(len(obj.questions), 1)
        self.assertEqual(obj.questions[0].correct_answer, "3e8 m/s")
        self.assertEqual(metrics.direct_successes, 1)

    def test_truncated_json_repair(self):
        # Truncated before closing brackets and quotes
        raw = """
        {
            "title": "Truncated Chemistry Quiz",
            "questions": [
                {
                    "question_text": "What is the atomic number of Hydrogen?",
                    "question_type": "short_answer",
                    "correct_answer": "1",
                    "explanation": "Hydrogen is the first element on the periodic table",
                    "difficulty": "beginner",
                    "topic": "hydrogen
        """
        # Note the unclosed quote on topic, and unclosed question object + list + main object.
        obj = parse_structured_output(raw, QuizPayloadSchema)
        self.assertEqual(obj.title, "Truncated Chemistry Quiz")
        self.assertEqual(len(obj.questions), 1)
        self.assertEqual(obj.questions[0].topic, "hydrogen")
        self.assertEqual(metrics.recovered_successes, 1)

    def test_single_quotes_repair(self):
        raw = """
        {
            'deck_name': 'Spanish Vocab',
            'cards': [
                {
                    'front': 'Hola',
                    'back': 'Hello',
                    'tags': ['greetings', 'basics']
                }
            ]
        }
        """
        obj = parse_structured_output(raw, FlashcardPayloadSchema)
        self.assertEqual(obj.deck_name, "Spanish Vocab")
        self.assertEqual(obj.cards[0].front, "Hola")
        self.assertEqual(metrics.recovered_successes, 1)

    def test_hallucinated_extra_fields(self):
        raw = """
        {
            "title": "Math Quiz",
            "questions": [{"question_text": "What is 2+2?", "question_type": "short_answer", "correct_answer": "4"}],
            "generated_by": "ollama-phi3",
            "model_version": "v1.2",
            "unsupported_hyper_parameter": 42
        }
        """
        obj = parse_structured_output(raw, QuizPayloadSchema)
        self.assertEqual(obj.title, "Math Quiz")
        self.assertEqual(len(obj.questions), 1)
        self.assertEqual(metrics.direct_successes, 1)

    def test_missing_required_fields(self):
        # Missing 'question_text' inside question
        raw = """
        {
            "title": "Incomplete Quiz",
            "questions": [
                {
                    "question_type": "short_answer",
                    "explanation": "Basic arithmetic"
                }
            ]
        }
        """
        with self.assertRaises(ValidationError):
            parse_structured_output(raw, QuizPayloadSchema)
        self.assertEqual(metrics.total_failures, 1)

    def test_empty_response(self):
        raw = ""
        with self.assertRaises(ValidationError):
            parse_structured_output(raw, QuizPayloadSchema)
        self.assertEqual(metrics.total_failures, 1)

    def test_llm_regeneration_success(self):
        # First response is completely invalid
        bad_raw = "This is some conversational text instead of JSON."

        # Second response is valid
        good_raw = """
        {
            "title": "Regenerated Quiz",
            "questions": [
                {
                    "question_text": "Is Python interpreted?",
                    "question_type": "true_false",
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": "Python is executed line by line.",
                    "topic": "python",
                    "difficulty": "beginner"
                }
            ]
        }
        """

        calls = []

        def mock_llm_call(system, history, user):
            calls.append((system, history, user))
            return good_raw, 100, 500.0

        args = {
            "system_prompt": "You are a quiz writer.",
            "history": [],
            "user_message": "Make a quiz about Python.",
        }

        obj = parse_structured_output(
            bad_raw,
            QuizPayloadSchema,
            llm_call_fn=mock_llm_call,
            original_prompt_args=args,
            max_regenerations=1,
        )
        self.assertEqual(obj.title, "Regenerated Quiz")
        self.assertEqual(len(calls), 1)
        self.assertIn("SYSTEM WARNING", calls[0][2])
        self.assertEqual(metrics.regenerations, 1)
        self.assertEqual(metrics.recovered_successes, 1)

    def test_true_false_without_options_uses_the_fixed_pair(self):
        quiz = QuizPayloadSchema.model_validate(
            {
                "title": "Inertia",
                "questions": [
                    {
                        "question_text": "Mass measures inertia.",
                        "question_type": "true_false",
                        "options": None,
                        "correct_answer": "true",
                    }
                ],
            }
        )
        self.assertEqual(quiz.questions[0].options, ["True", "False"])
        self.assertEqual(quiz.questions[0].correct_answer, "True")

    def test_choice_questions_without_usable_options_still_fail(self):
        for question_type, answer in (("multiple_choice", "Mass"), ("true_false", "Maybe")):
            with self.assertRaises(ValidationError):
                QuizPayloadSchema.model_validate(
                    {
                        "title": "Inertia",
                        "questions": [
                            {
                                "question_text": "Which quantity measures inertia?",
                                "question_type": question_type,
                                "options": None,
                                "correct_answer": answer,
                            }
                        ],
                    }
                )


if __name__ == "__main__":
    unittest.main()


def test_flashcard_tags_drop_prompt_bookkeeping():
    """Goldfish test F11: a card tag read "(Citation Index: 3)"."""
    from sentio.ai.structured_parser import FlashcardItem

    card = FlashcardItem(front="ATP", back="Energy carrier", tags=["ATP", "(Citation Index: 3)"])
    assert card.tags == ["ATP"]
