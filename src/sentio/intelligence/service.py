import logging
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

from sqlalchemy import text

from sentio.flashcards import fsrs
from sentio.intelligence.adaptation import AdaptationEngine
from sentio.intelligence.confidence import ConfidenceEngine
from sentio.intelligence.explanation import ExplanationEngine
from sentio.intelligence.forgetting import ForgettingEngine
from sentio.intelligence.learning_path import LearningPathEngine
from sentio.intelligence.mastery import MasteryEngine
from sentio.intelligence.misconception import MisconceptionEngine
from sentio.intelligence.models import LearnerModel, SessionSummaryReport, StudyRecommendation
from sentio.intelligence.progress import ProgressEngine
from sentio.intelligence.recommendation import RecommendationEngine
from sentio.intelligence.session_summary import SessionSummaryEngine

logger = logging.getLogger(__name__)


def study_streak(timestamps, now):
    """Consecutive local calendar days with a session, ending today or yesterday."""
    days = {date.fromtimestamp(t) for t in timestamps if t}
    day = date.fromtimestamp(now)
    if day not in days:
        day -= timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


class IntelligenceService:
    """
    Lightweight orchestration service for the Adaptive Learning Intelligence Platform.
    Coordinates all independent engines to maintain student models, recommend paths,
    and adapt tutoring.
    """

    def __init__(self, sm: Any):
        self.sm = sm
        self.mastery_engine = MasteryEngine()
        self.confidence_engine = ConfidenceEngine()
        self.forgetting_engine = ForgettingEngine()
        self.misconception_engine = MisconceptionEngine()
        self.recommendation_engine = RecommendationEngine()
        self.learning_path_engine = LearningPathEngine()
        self.adaptation_engine = AdaptationEngine()
        self.progress_engine = ProgressEngine()
        self.explanation_engine = ExplanationEngine()
        self.session_summary_engine = SessionSummaryEngine()

    def build_learner_model(self, student_id: str) -> LearnerModel:
        """
        Gathers database evidence to build a continuously evolving student model.
        """
        # Ensure database is loaded

        # 1. Fetch raw sql tables data
        engine = self.sm.persister._engine
        with engine.connect() as conn:
            # Quiz attempts
            quizzes_rows = conn.execute(
                text(
                    "SELECT topic, correct, question_text, student_answer, timestamp FROM quiz_attempts WHERE student_id = :sid"
                ),
                {"sid": student_id},
            ).fetchall()

            # Student knowledge records
            knowledge_rows = conn.execute(
                text(
                    "SELECT topic_id, mastery_score, attempts_count, consecutive_correct, last_attempt_at FROM student_knowledge WHERE student_id = :sid"
                ),
                {"sid": student_id},
            ).fetchall()

            # Flashcards
            flashcards_rows = conn.execute(
                text(
                    "SELECT card_id, topic_id, deck_id, interval_days, repetition_count, ease_factor, next_review_at, stability, difficulty, last_review_at FROM flashcards WHERE student_id = :sid"
                ),
                {"sid": student_id},
            ).fetchall()

            # Sessions
            sessions_rows = conn.execute(
                text(
                    "SELECT session_id, topic, created_at, data_json FROM sessions WHERE student_id = :sid"
                ),
                {"sid": student_id},
            ).fetchall()

        # Group data by topic
        topic_quizzes: Dict[str, List[dict]] = {}
        for r in quizzes_rows:
            topic_quizzes.setdefault(r[0], []).append(
                {"correct": r[1], "question_text": r[2], "student_answer": r[3], "timestamp": r[4]}
            )

        topic_flashcards: Dict[str, List[dict]] = {}
        due_flashcards_count: Dict[str, int] = {}
        current_time = time.time()
        for r in flashcards_rows:
            card = {
                "card_id": r[0],
                "topic_id": r[1],
                "deck_id": r[2],
                "interval_days": r[3],
                "repetition_count": r[4],
                "ease_factor": r[5],
                "next_review_at": r[6],
                "stability": r[7],
                "difficulty": r[8],
                "last_review_at": r[9],
            }
            card["recall_probability"] = fsrs.recall_probability(card, current_time)
            topic_flashcards.setdefault(r[1], []).append(card)
            if r[6] <= current_time:
                due_flashcards_count[r[1]] = due_flashcards_count.get(r[1], 0) + 1

        # Process topic metrics
        topic_mastery: Dict[str, float] = {}
        confidence: Dict[str, float] = {}
        forgetting_risk: Dict[str, float] = {}
        knowledge_stability: Dict[str, float] = {}
        weak_concepts: List[str] = []
        strong_concepts: List[str] = []
        misconceptions: Dict[str, List[str]] = {}
        readiness: Dict[str, bool] = {}

        # Prerequisite knowledge graph
        prereqs, topic_prereq_map = self._get_knowledge_graph()

        # Build raw masteries
        raw_mastery: Dict[str, float] = {}
        for r in knowledge_rows:
            topic_id, mastery, attempts, consec, last_at = r
            raw_mastery[topic_id] = mastery

        # Propagate mastery down the graph
        topic_mastery = self.mastery_engine.propagate_mastery(raw_mastery, topic_prereq_map)

        for r in knowledge_rows:
            topic_id, mastery, attempts, consec, last_at = r
            # Adjusted mastery after propagation
            adj_mastery = topic_mastery.get(topic_id, mastery)

            # Compute Confidence
            q_scores = [float(q["correct"]) for q in topic_quizzes.get(topic_id, [])]
            confidence[topic_id] = self.confidence_engine.calculate_confidence(
                mastery=adj_mastery,
                last_attempt_at=last_at,
                current_time=current_time,
                attempts_count=attempts,
                quiz_scores=q_scores,
            )

            # Forgetting risk: FSRS recall probability of reviewed cards, else a quiz estimate
            reviewed = [
                (f["recall_probability"], fsrs.memory_state(f)[0])
                for f in topic_flashcards.get(topic_id, [])
                if f["recall_probability"] is not None
            ]
            if reviewed:
                risk = 1 - sum(r for r, _ in reviewed) / len(reviewed)
                stability = sum(s for _, s in reviewed) / len(reviewed)
            else:
                risk, stability = self.forgetting_engine.calculate_forgetting_risk(
                    last_attempt_at=last_at,
                    current_time=current_time,
                    repetition_count=attempts,
                    mastery=adj_mastery,
                )
            forgetting_risk[topic_id] = risk
            knowledge_stability[topic_id] = stability

            # Check weak/strong categories
            if adj_mastery < 0.5:
                weak_concepts.append(topic_id)
            elif adj_mastery >= 0.8:
                strong_concepts.append(topic_id)

            # Detect Misconceptions
            # Approximate hint counts and exchanges from session JSONs
            hints = 0
            exchanges = 0
            for s in sessions_rows:
                import json

                try:
                    data = json.loads(s[3]) if s[3] else {}
                    if s[1] == topic_id:
                        exchanges += data.get("total_exchanges", 0)
                        # Estimate hints as 20% of exchanges if no raw field
                        hints += int(exchanges * 0.2)
                except Exception:
                    pass

            misconceptions[topic_id] = self.misconception_engine.detect_misconceptions(
                topic_id=topic_id,
                quiz_attempts=topic_quizzes.get(topic_id, []),
                hints_requested=hints,
                total_exchanges=exchanges,
            )

            # Check Readiness
            readiness[topic_id] = self.learning_path_engine.evaluate_readiness(
                topic_id=topic_id,
                prereqs=topic_prereq_map.get(topic_id, []),
                topic_mastery=topic_mastery,
            )

        # 2. Build review priorities based on forgetting risk + weak mastery
        review_priorities = []
        for topic in topic_mastery:
            weight_due = 0.5 if due_flashcards_count.get(topic, 0) > 0 else 0.0
            priority_score = (1.0 - confidence.get(topic, 0.5)) * (1.0 + weight_due)
            review_priorities.append((topic, priority_score))
        review_priorities.sort(key=lambda x: x[1], reverse=True)
        review_priorities_list = [x[0] for x in review_priorities]

        # 3. Overall average mastery
        overall_mastery = sum(topic_mastery.values()) / len(topic_mastery) if topic_mastery else 0.0

        # 4. Progress timeline reconstruction
        timeline = []
        for s in sessions_rows:
            timeline.append(
                {
                    "session_id": s[0],
                    "timestamp": s[2],
                    "overall_mastery": overall_mastery,
                    "knowledge_stability": dict(knowledge_stability),
                }
            )

        progress_metrics = self.progress_engine.calculate_progress_metrics(
            timeline, overall_mastery
        )

        # Build LearnerModel instance
        return LearnerModel(
            student_id=student_id,
            overall_mastery=overall_mastery,
            topic_mastery=topic_mastery,
            confidence=confidence,
            learning_velocity=progress_metrics["velocity"],
            forgetting_risk=forgetting_risk,
            knowledge_stability=knowledge_stability,
            weak_concepts=weak_concepts,
            strong_concepts=strong_concepts,
            misconceptions=misconceptions,
            review_priorities=review_priorities_list,
            learning_streak=study_streak([r[2] for r in sessions_rows], current_time),
            avg_response_quality=overall_mastery,
            preferred_explanation_style="analogy" if "simplify" in weak_concepts else "standard",
            preferred_difficulty="beginner" if weak_concepts else "intermediate",
            engagement_score=0.75,
            cognitive_load_estimate=progress_metrics.get("concept_stability_average", 0.5) * 0.1,
            readiness_for_assessment=readiness,
            historical_progress_timeline=timeline,
        )

    def generate_recommendations(self, student_id: str) -> List[StudyRecommendation]:
        """
        Creates explainable next actions ranked by priority score.
        """
        model = self.build_learner_model(student_id)
        prereqs, topic_prereq_map = self._get_knowledge_graph()

        all_recs = []
        # Query all decks for this student
        decks = self.sm.list_sessions(student_id=student_id)
        has_deck_map = {d.get("topic"): True for d in decks if d.get("topic")}

        for topic, mastery in model.topic_mastery.items():
            conf = model.confidence.get(topic, 0.5)
            # Count due cards
            due_cards = 0
            with self.sm.persister._engine.connect() as conn:
                due_cards = (
                    conn.execute(
                        text(
                            "SELECT COUNT(*) FROM flashcards WHERE student_id = :sid AND topic_id = :tid AND next_review_at <= :now"
                        ),
                        {"sid": student_id, "tid": topic, "now": time.time()},
                    ).scalar()
                    or 0
                )

            recs = self.recommendation_engine.generate_recommendations(
                student_id=student_id,
                topic_id=topic,
                mastery=mastery,
                confidence=conf,
                due_flashcards_count=due_cards,
                has_deck=has_deck_map.get(topic, False),
                prereqs=topic_prereq_map.get(topic, []),
                prereq_mastery=model.topic_mastery,
            )
            all_recs.extend(recs)

        # Sort recommendations globally by priority score
        all_recs.sort(key=lambda x: x.priority_score, reverse=True)
        return all_recs

    def generate_learning_path(self, student_id: str, subject: str = "general") -> List[str]:
        """
        Generates a sequenced list of topics based on prerequisite topology.
        """
        # Get all topics seeded in the system
        all_topics = []
        with self.sm.persister._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT topic_id FROM topics WHERE subject = :sub"), {"sub": subject}
            ).fetchall()
            all_topics = [r[0] for r in rows]

        if not all_topics:
            all_topics = ["limits", "derivatives", "newtons_laws", "recursion"]

        prereqs, _ = self._get_knowledge_graph()
        return self.learning_path_engine.sequence_topics(all_topics, prereqs)

    def generate_session_summary(self, session_id: str) -> SessionSummaryReport:
        """
        Compiles the progress metrics and recommendations for a finished session.
        """
        session = self.sm.get_session(session_id)
        if not session:
            # Try loading from DB
            data = self.sm.persister.load_session_data(session_id)
            if not data:
                raise KeyError(f"Session summary failed: session {session_id} not found.")
            session = self.sm.get_or_raise(session_id)

        # Get quiz attempts for this session
        quiz_attempts = []
        with self.sm.persister._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT topic, correct, question_text, student_answer, timestamp FROM quiz_attempts WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).fetchall()
            quiz_attempts = [
                {
                    "topic": r[0],
                    "correct": r[1],
                    "question_text": r[2],
                    "student_answer": r[3],
                    "timestamp": r[4],
                }
                for r in rows
            ]

        # Get emotion logs from DB
        emotion_events = []
        with self.sm.persister._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT timestamp, emotion, learning_state, confidence, strategy FROM emotion_events WHERE session_id = :sid"
                ),
                {"sid": session_id},
            ).fetchall()
            emotion_events = [
                {
                    "timestamp": r[0],
                    "emotion": r[1],
                    "learning_state": r[2],
                    "confidence": r[3],
                    "strategy": r[4],
                }
                for r in rows
            ]

        # Fallback to timeline if db empty
        if not emotion_events and session.emotion_timeline:
            emotion_events = session.emotion_timeline.all_as_dicts()

        # Compute summary
        topic = session.topic
        model = self.build_learner_model(session.student_id)
        retention = model.forgetting_risk.get(topic, 0.5)

        due_date = time.time() + 86400.0
        # Check next review date from flashcards
        with self.sm.persister._engine.connect() as conn:
            due_date = conn.execute(
                text(
                    "SELECT MIN(next_review_at) FROM flashcards WHERE student_id = :sid AND topic_id = :tid"
                ),
                {"sid": session.student_id, "tid": topic},
            ).scalar() or (time.time() + 86400.0)

        # Recommendations list for UI display
        recs = [r.to_dict() for r in self.generate_recommendations(session.student_id)[:2]]

        return self.session_summary_engine.compile_summary(
            session_id=session_id,
            student_id=session.student_id,
            subject=session.subject,
            duration_min=session.duration_minutes,
            topics_covered=session.topics_covered,
            quiz_attempts=quiz_attempts,
            emotion_events=emotion_events,
            topic_retention={topic: retention},
            next_reviews={topic: due_date},
            recommendations=recs,
        )

    def _get_knowledge_graph(self) -> Tuple[List[Tuple[str, str]], Dict[str, List[str]]]:
        """
        Loads prerequisite relationships from the SQLite topic_prerequisites table.
        Seeds standard relationships if the database table is empty.
        """
        prerequisites = []
        topic_prereq_map: Dict[str, List[str]] = {}

        engine = self.sm.persister._engine
        with engine.connect() as conn:
            # Ensure base topics are in topics table first
            self._seed_default_topics(conn)

            rows = conn.execute(
                text("SELECT parent_topic_id, child_topic_id FROM topic_prerequisites")
            ).fetchall()
            prerequisites = [(r[0], r[1]) for r in rows]

        # Seed defaults if database table was empty
        if not prerequisites:
            defaults = [
                ("limits", "derivatives"),
                ("algebra", "linear_equations"),
                ("linear_equations", "quadratic_equations"),
                ("quadratic_equations", "functions"),
            ]
            with engine.connect() as conn:
                for parent, child in defaults:
                    try:
                        # Verify both topics exist in topics table
                        conn.execute(
                            text(
                                "INSERT OR IGNORE INTO topics (topic_id, subject, display_name, description) VALUES (:tid, 'mathematics', :name, '')"
                            ),
                            {"tid": parent, "name": parent.replace("_", " ").title()},
                        )
                        conn.execute(
                            text(
                                "INSERT OR IGNORE INTO topics (topic_id, subject, display_name, description) VALUES (:tid, 'mathematics', :name, '')"
                            ),
                            {"tid": child, "name": child.replace("_", " ").title()},
                        )
                        # Insert prerequisite link
                        conn.execute(
                            text(
                                "INSERT OR IGNORE INTO topic_prerequisites (parent_topic_id, child_topic_id) VALUES (:parent, :child)"
                            ),
                            {"parent": parent, "child": child},
                        )
                    except Exception as e:
                        logger.error(f"Error seeding topic prerequisite: {e}")
                conn.commit()
            prerequisites = defaults

        # Populate mapping
        for parent, child in prerequisites:
            topic_prereq_map.setdefault(child, []).append(parent)

        return prerequisites, topic_prereq_map

    def _seed_default_topics(self, conn):
        """Helper to ensure base curriculum topics exist in SQLite."""
        topics = [
            ("limits", "mathematics"),
            ("derivatives", "mathematics"),
            ("algebra", "mathematics"),
            ("linear_equations", "mathematics"),
            ("quadratic_equations", "mathematics"),
            ("functions", "mathematics"),
            ("newtons_laws", "physics"),
            ("recursion", "computer_science"),
        ]
        for tid, sub in topics:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO topics (topic_id, subject, display_name, description) VALUES (:tid, :sub, :name, '')"
                ),
                {"tid": tid, "sub": sub, "name": tid.replace("_", " ").title()},
            )
        conn.commit()
