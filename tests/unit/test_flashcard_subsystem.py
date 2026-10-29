"""
test_flashcard_subsystem.py -- Unit and Integration Tests for Flashcard Subsystem (Phases D3 & D4)
=============================================================================================
Verifies:
  - Flashcard deck creation
  - AI-generated flashcards from context
  - Spaced repetition queue retrieval
  - SM-2 algorithm calculations (success & failure)
  - Student memory loop integration (mastery updates)
  - Tutor chat struggle recommendation hook
"""

import unittest

from sentio.flashcards.service import FlashcardService
from sentio.tutor.agent import TutorAgent


class TestFlashcardSubsystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = TutorAgent()
        cls.agent.load()
        cls.flashcard_service = FlashcardService(cls.agent)

        cls.student_id = "stu_test_cards_001"
        cls.agent.sm.ensure_student_exists(cls.student_id)

        cls.session = cls.agent.sm.create_session(
            student_id=cls.student_id,
            subject="physics",
            topic="thermodynamics",
            difficulty="intermediate",
        )
        cls.session_id = cls.session.session_id

    def test_01_deck_creation(self):
        deck_id = self.flashcard_service.create_deck(self.student_id, "Physics Formulae")
        self.assertIsNotNone(deck_id)
        self.__class__.deck_id = deck_id

    def test_02_card_generation(self):
        # Generate 3 cards
        cards_payload = self.flashcard_service.generate_flashcards(
            student_id=self.student_id,
            deck_id=self.__class__.deck_id,
            topic_id="thermodynamics",
            num_cards=3,
        )

        self.assertIn("deck_name", cards_payload)
        self.assertEqual(len(cards_payload["cards"]), 3)
        self.assertIn("front", cards_payload["cards"][0])
        self.assertIn("back", cards_payload["cards"][0])

    def test_03_due_reviews_queue(self):
        due_cards = self.flashcard_service.get_due_reviews(self.student_id)
        self.assertGreaterEqual(len(due_cards), 3)
        # Store a card for review tests
        self.__class__.card_to_test = due_cards[0]

    def test_04_sm2_review_success(self):
        card = self.__class__.card_to_test
        card_id = card["card_id"]

        # Start mastery check
        from sqlalchemy import text

        with self.agent.sm.persister._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": self.student_id, "tid": "thermodynamics"},
            ).fetchone()
        starting_mastery = row[0] if row else 0.0

        # Review success (score 4)
        review_res = self.flashcard_service.review_card(card_id, quality_score=4)

        self.assertEqual(review_res["card_id"], card_id)
        self.assertEqual(review_res["next_interval_days"], 1)  # first rep is 1 day
        self.assertEqual(review_res["repetition_count"], 1)
        self.assertGreater(review_res["ease_factor"], 1.3)

        # Verify mastery score boosted in DB
        with self.agent.sm.persister._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": self.student_id, "tid": "thermodynamics"},
            ).fetchone()
        ending_mastery = row[0]
        self.assertGreater(ending_mastery, starting_mastery)

    def test_05_sm2_review_failure(self):
        card = self.__class__.card_to_test
        card_id = card["card_id"]

        # Fetch mastery
        from sqlalchemy import text

        with self.agent.sm.persister._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": self.student_id, "tid": "thermodynamics"},
            ).fetchone()
        starting_mastery = row[0]

        # Review failure (score 1)
        review_res = self.flashcard_service.review_card(card_id, quality_score=1)

        self.assertEqual(review_res["card_id"], card_id)
        self.assertEqual(review_res["next_interval_days"], 1)
        self.assertEqual(review_res["repetition_count"], 0)  # reset

        # Verify mastery score demoted in DB
        with self.agent.sm.persister._engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT mastery_score FROM student_knowledge WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": self.student_id, "tid": "thermodynamics"},
            ).fetchone()
        ending_mastery = row[0]
        self.assertLess(ending_mastery, starting_mastery)

    def test_06_tutor_suggestion_hook(self):
        # Clear chat history for clean run
        self.agent.nlp._get_history(self.session_id).clear()

        # Ask first time
        res1 = self.agent.chat(self.session_id, "what is entropy")
        self.assertNotIn("💡 *Tip: You seem to be working on", res1.tutor_response.text)

        # Ask second time
        res2 = self.agent.chat(self.session_id, "what is entropy")
        self.assertIn(
            "💡 *Tip: You seem to be working on 'Entropy'. Would you like to add this to your flashcard deck?*",
            res2.tutor_response.text,
        )


if __name__ == "__main__":
    unittest.main()
