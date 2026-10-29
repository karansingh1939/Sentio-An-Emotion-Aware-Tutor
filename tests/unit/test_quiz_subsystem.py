"""
test_quiz_subsystem.py -- Unit and Integration Tests for Quiz Subsystem (Phases D1 & D2)
========================================================================================
Verifies:
  - Quiz generation and Pydantic validation
  - Database saving and retrieval of quizzes
  - Grading of MCQs, True/False, and Short Answers
  - Dynamic EMA mastery updates in database
  - Mistake frequency logging
  - Observability metric visibility
"""

import unittest

from sentio.ai.structured_parser import metrics as parser_metrics
from sentio.quiz.service import QuizService
from sentio.tutor.agent import TutorAgent


class TestQuizSubsystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize TutorAgent in test mode with SQLite
        cls.agent = TutorAgent()
        cls.agent.load()
        cls.quiz_service = QuizService(cls.agent)

        # Ensure we have a clean student
        cls.student_id = "stu_test_quiz_001"
        cls.agent.sm.ensure_student_exists(cls.student_id)

        # Create a test session
        cls.session = cls.agent.sm.create_session(
            student_id=cls.student_id,
            subject="physics",
            topic="thermodynamics",
            difficulty="intermediate",
        )
        cls.session_id = cls.session.session_id

    def test_01_quiz_generation_and_persistence(self):
        # Reset parser metrics
        parser_metrics.total_attempts = 0
        parser_metrics.direct_successes = 0

        # Generate quiz
        quiz = self.quiz_service.generate_quiz(
            student_id=self.student_id,
            session_id=self.session_id,
            subject="physics",
            topic="thermodynamics",
            difficulty="intermediate",
            num_questions=3,
        )

        self.assertIn("quiz_id", quiz)
        self.assertIn("title", quiz)
        self.assertEqual(len(quiz["questions"]), 3)

        # Store quiz_id for scoring test
        self.__class__.quiz_id = quiz["quiz_id"]
        self.__class__.questions = quiz["questions"]

        # Verify it was saved to DB and can be retrieved
        saved_quiz = self.agent.sm.get_quiz(quiz["quiz_id"])
        self.assertIsNotNone(saved_quiz)
        self.assertEqual(saved_quiz["title"], quiz["title"])
        self.assertEqual(len(saved_quiz["questions"]), 3)

        # Verify parser metrics tracked it
        self.assertGreaterEqual(parser_metrics.total_attempts, 1)

    def test_02_quiz_scoring_and_memory_updates(self):
        quiz_id = self.__class__.quiz_id
        questions = self.__class__.questions

        # Look up starting mastery (should be 0.0)
        from sqlalchemy import text

        with self.agent.sm.persister._engine.connect() as conn:
            starting_row = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": self.student_id, "tid": "thermodynamics"},
            ).fetchone()
        starting_mastery = starting_row[0] if starting_row else 0.0

        # Simulate answers: Question 0 is correct, Question 1 is incorrect, Question 2 is correct
        student_answers = {}

        # MCQ/TF check
        q0 = questions[0]
        student_answers[0] = q0["correct_answer"]  # Correct

        questions[1]
        student_answers[1] = "Completely incorrect response"  # Incorrect

        q2 = questions[2]
        student_answers[2] = q2["correct_answer"]  # Correct

        # Submit scoring
        result = self.quiz_service.score_quiz(
            quiz_id=quiz_id, student_answers=student_answers, session_id=self.session_id
        )

        self.assertIn("total_score", result)
        self.assertIn("passed", result)
        self.assertEqual(len(result["feedback"]), 3)
        self.assertTrue(result["feedback"][0]["is_correct"])
        self.assertFalse(result["feedback"][1]["is_correct"])
        self.assertTrue(result["feedback"][2]["is_correct"])

        # Verify mastery score was updated via EMA in the database
        with self.agent.sm.persister._engine.connect() as conn:
            ending_row = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": self.student_id, "tid": "thermodynamics"},
            ).fetchone()
        self.assertIsNotNone(ending_row)
        ending_mastery = ending_row[0]
        self.assertNotEqual(starting_mastery, ending_mastery)

        # Verify mistakes were logged in the quiz_attempts database table
        with self.agent.sm.persister._engine.connect() as conn:
            fails = conn.execute(
                text("SELECT COUNT(*) FROM quiz_attempts WHERE student_id = :sid AND correct = 0"),
                {"sid": self.student_id},
            ).scalar()
        self.assertGreaterEqual(fails, 1)


if __name__ == "__main__":
    unittest.main()
