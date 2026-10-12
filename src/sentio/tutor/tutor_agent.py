"""
tutor_agent.py -- Core Orchestrator for Emotion-Aware AI Tutor
==============================================================
The TutorAgent is the single entry-point that wires together every
subsystem and produces a final tutoring response for each student turn.

Pipeline per exchange
---------------------
1. Receive student message + live webcam frame
2. EmotionDetector  -> EmotionResult  (what is the student feeling?)
3. SessionManager   -> record emotion, get current state snapshot
4. KnowledgeBase    -> retrieve curriculum content (RAG)
5. NLPEngine        -> build prompt + call LLM -> TutorResponse
6. SessionManager   -> record exchange metrics
7. Return assembled TutorResponse to API layer

Architecture
------------
TutorAgent
  |-- EmotionDetector   (CV pipeline)
  |-- KnowledgeBase     (curriculum RAG)
  |-- NLPEngine         (LLM abstraction)
  |-- SessionManager    (state + persistence)

Usage
-----
    agent = TutorAgent()
    agent.load()

    session = agent.start_session(
        student_id="stu_001",
        subject="mathematics",
        topic="derivatives",
        difficulty="beginner",
    )

    response = agent.chat(
        session_id=session.session_id,
        student_message="I don't understand the chain rule",
        frame=webcam_frame,          # numpy BGR array, or None
    )
    print(response.full_text())
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from sentio.ai.emotion_detector import EmotionDetector, EmotionResult
from sentio.ai.nlp_engine import NLPEngine, TutorResponse
from sentio.config import emotion_cfg, tutor_cfg
from sentio.rag.knowledge_base import KnowledgeBase
from sentio.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# AGENT RESPONSE WRAPPER
# ─────────────────────────────────────────────


@dataclass
class AgentResponse:
    """
    Full response package returned to the API / UI layer.
    Bundles the LLM reply with live session state metadata
    so the frontend can render the emotion overlay, difficulty
    badge, strategy indicator, etc.
    """

    # Core reply
    tutor_response: TutorResponse

    # Live session snapshot
    session_id: str
    learning_state: str
    strategy: str
    difficulty: str
    engagement_score: float

    # Emotion detection
    detected_emotion: str
    emotion_confidence: float
    emotion_scores: Dict[str, float]

    # Curriculum metadata
    subject: str
    topic: str
    topics_covered: list
    total_latency_ms: float
    source_citations: List[dict] = field(default_factory=list)

    # Timing
    timestamp: float = field(default_factory=time.time)
    total_exchanges: int = 0
    duration_minutes: float = 0.0

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "text": self.tutor_response.text,
            "answer_mode": self.tutor_response.backend_used,
            "follow_up": self.tutor_response.follow_up_question,
            "encouragement": self.tutor_response.encouragement,
            "suggested_topic": self.tutor_response.suggested_topic,
            "learning_state": self.learning_state,
            "strategy": self.strategy,
            "difficulty": self.difficulty,
            "engagement_score": round(self.engagement_score, 3),
            "detected_emotion": self.detected_emotion,
            "emotion_confidence": round(self.emotion_confidence, 3)
            if self.emotion_confidence is not None
            else 0.0,
            "emotion_scores": {k: round(v, 3) for k, v in self.emotion_scores.items()}
            if self.emotion_scores
            else {},
            "subject": self.subject,
            "topic": self.topic,
            "topics_covered": self.topics_covered,
            "source_citations": self.source_citations,
            "total_latency_ms": round(self.total_latency_ms, 1),
            "total_exchanges": self.total_exchanges,
            "duration_minutes": round(self.duration_minutes, 2),
            "timestamp": self.timestamp,
        }


# ─────────────────────────────────────────────
# TUTOR AGENT
# ─────────────────────────────────────────────


class TutorAgent:
    """
    Orchestrates the full Emotion-Aware AI Tutor pipeline.

    All heavy subsystems are lazy-loaded on .load() so the
    agent can be instantiated cheaply at import time.
    """

    def __init__(
        self,
        detector: Optional[EmotionDetector] = None,
        kb: Optional[KnowledgeBase] = None,
        nlp: Optional[NLPEngine] = None,
        sm: Optional[SessionManager] = None,
    ):
        self.detector = detector or EmotionDetector()
        self.kb = kb or KnowledgeBase()
        self.nlp = nlp or NLPEngine()
        self.sm = sm or SessionManager()
        self.intelligence = None
        self.orchestrator = None
        self._loaded = False
        self.startup_errors = {}
        self._camera_attempted = False
        from threading import RLock

        self._camera_lock = RLock()

    # ── Lifecycle ──────────────────────────────

    def load(self):
        """
        Load all subsystems. Call once at application startup.
        Safe to call multiple times (idempotent).
        """
        if self._loaded:
            return

        logger.info("TutorAgent: loading subsystems...")
        t0 = time.perf_counter()

        self.sm.load()
        for name, service in (("retrieval", self.kb), ("ai", self.nlp)):
            try:
                service.load()
            except Exception:
                self.startup_errors[name] = "Initialization failed; see local diagnostics."
                logger.exception("Optional %s initialization failed", name)

        from sentio.intelligence.intelligence_service import IntelligenceService

        self.intelligence = IntelligenceService(self.sm)

        from sentio.tutor.orchestrator import SentioOrchestrator

        self.orchestrator = SentioOrchestrator(self)

        elapsed = (time.perf_counter() - t0) * 1000
        self._loaded = True
        logger.info("TutorAgent ready. Load time: %.0f ms", elapsed)

    def _require_loaded(self):
        if not self._loaded:
            raise RuntimeError("TutorAgent not loaded. Call agent.load() before use.")

    # ── Session Management ─────────────────────

    def start_session(
        self,
        student_id,
        subject,
        topic,
        difficulty="beginner",
        metadata=None,
    ):
        """
        Create a new tutoring session and return the Session object.

        Args:
            student_id  : Unique student identifier string
            subject     : e.g. "mathematics"
            topic       : e.g. "derivatives"
            difficulty  : "beginner" | "intermediate" | "advanced"
            metadata    : Optional dict of extra fields (name, grade, etc.)

        Returns:
            Session
        """
        self._require_loaded()
        session = self.sm.create_session(
            student_id=student_id,
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            metadata=metadata or {},
        )
        logger.info(
            "Session started: %s | %s/%s [%s]",
            session.session_id[:8],
            subject,
            topic,
            difficulty,
        )
        return session

    def end_session(self, session_id):
        """
        Close a session, persist it, and return the analytics report.

        Returns:
            SessionAnalytics
        """
        self._require_loaded()
        analytics = self.sm.close_session(session_id)
        self.nlp.clear_history(session_id)
        self.kb.reset_session(session_id)
        self.detector.clear_session(session_id)
        logger.info("Session ended: %s", session_id[:8])
        return analytics

    def pause_session(self, session_id):
        self.sm.pause_session(session_id)

    def resume_session(self, session_id):
        self.sm.resume_session(session_id)

    # ── Core Chat Method ───────────────────────

    def chat(
        self,
        session_id,
        student_message,
        frame=None,
        quiz_answer=None,
        quiz_correct=None,
        response_time_sec=0.0,
        defer_turn=False,
    ):
        """
        Process one student turn and return an AgentResponse.

        Args:
            session_id      : Active session ID
            student_message : Student's text input (str)
            frame           : Optional BGR numpy array from webcam.
                              If None, the last known emotion is reused.
            quiz_answer     : Optional raw answer string (not graded here)
            quiz_correct    : Optional bool -- was the student's answer correct?
            response_time_sec: How long the student took to answer (for quiz metrics)

        Returns:
            AgentResponse
        """
        self._require_loaded()
        wall_start = time.perf_counter()

        session = self.sm.get_or_raise(session_id)
        if not session.is_active:
            raise RuntimeError(
                "Session %s is not active (status=%s)." % (session_id[:8], session.status.value)
            )

        # ── Step 1: Emotion Detection ───────────
        emotion_result = self._detect_emotion(frame, session_id=session_id)

        # ── Step 2: Record emotion + maybe adapt difficulty ──
        if not defer_turn:
            self.sm.record_emotion(
                session_id,
                emotion_result,
                strategy_active=session.current_strategy,
            )

            # ── Step 3: Record quiz result if provided ──
            if quiz_correct is not None:
                self.sm.record_quiz_attempt(
                    session_id=session_id,
                    correct=quiz_correct,
                    topic=session.topic,
                    response_time_sec=response_time_sec,
                    question_preview=student_message[:120],
                )

            # ── Step 4: Get live state snapshot ────
        state = self.sm.get_current_state(session_id)
        learning_state = state["learning_state"]
        strategy = state["strategy"]
        difficulty = state["difficulty"]
        engagement = state["engagement_score"]

        # ── Step 5: Invoke LangGraph Orchestrator ──
        history = self.nlp._get_history(session_id).to_list()

        initial_state = {
            "session_id": session_id,
            "student_id": session.student_id,
            "subject": state["subject"],
            "topic": state["topic"],
            "difficulty": difficulty,
            "learning_state": learning_state,
            "strategy": strategy,
            "user_message": student_message,
            "document_id": session.metadata.get("document_id"),
            "student_memory": "",
            "retrieved_content": None,
            "tone_instruction": "Be encouraging.",
            "history": history,
            "next_agent": "",
            "agent_response": None,
            "agent_timeline": [],
            "selected_route": [],
            "memory_usage_kb": 0.0,
            "retrieval_latency_ms": 0.0,
            "llm_latency_ms": 0.0,
            "total_latency_ms": 0.0,
        }

        final_state = self.orchestrator.execute(initial_state)
        tutor_resp = final_state["agent_response"]

        # Update NLPEngine conversation history (to maintain state across rounds)
        nlp_history = self.nlp._get_history(session_id)

        # Tutor recommendation hook for flashcards
        try:
            suggest_flashcard = self._check_flashcard_suggestion(
                session_id, student_message, nlp_history.to_list()
            )
            if suggest_flashcard:
                suggestion_text = f"\n\n💡 *Tip: You seem to be working on '{suggest_flashcard}'. Would you like to add this to your flashcard deck?*"
                tutor_resp.text += suggestion_text
        except Exception as e:
            logger.debug(f"Flashcard suggestion hook failed: {e}")

        if not defer_turn:
            nlp_history.add_user(student_message)
            nlp_history.add_assistant(tutor_resp.text)

            # ── Step 6: Record exchange metrics ─────
            self.sm.record_exchange(
                session_id=session_id,
                tokens=tutor_resp.tokens_used,
                latency_ms=tutor_resp.latency_ms,
            )

        # Save diagnostics logs to session manager
        diagnostics = {
            "selected_route": final_state["selected_route"],
            "agent_timeline": final_state["agent_timeline"],
            "memory_usage_kb": final_state["memory_usage_kb"],
            "retrieval_latency_ms": final_state["retrieval_latency_ms"],
            "llm_latency_ms": final_state["llm_latency_ms"],
            "total_latency_ms": final_state["total_latency_ms"],
        }

        citations = []
        ret_content = final_state.get("retrieved_content")
        if ret_content and hasattr(ret_content, "source_citations"):
            citations = ret_content.source_citations
            if ret_content.rag_diagnostics:
                diagnostics["rag_diagnostics"] = ret_content.rag_diagnostics

        if not defer_turn:
            self.sm.record_diagnostics(session_id, diagnostics)

        total_ms = (time.perf_counter() - wall_start) * 1000

        # ── Step 7: Assemble AgentResponse ──────
        return AgentResponse(
            tutor_response=tutor_resp,
            session_id=session_id,
            learning_state=final_state.get("learning_state", learning_state),
            strategy=final_state.get("strategy", strategy),
            difficulty=final_state.get("difficulty", difficulty),
            engagement_score=engagement,
            detected_emotion=emotion_result.emotion,
            emotion_confidence=emotion_result.confidence,
            emotion_scores=emotion_result.all_scores,
            subject=state["subject"],
            topic=state["topic"],
            topics_covered=state["topics_covered"],
            source_citations=citations,
            total_latency_ms=total_ms,
            total_exchanges=session.total_exchanges,
            duration_minutes=session.duration_minutes,
        )

    # ── Topic Switching ────────────────────────

    def switch_topic(self, session_id, new_topic, new_difficulty=None):
        """
        Change the active topic mid-session.
        Clears the NLP history so the LLM doesn't confuse contexts.

        Args:
            session_id     : Active session
            new_topic      : e.g. "limits"
            new_difficulty : Optional override; keeps current if None

        Returns:
            Updated state dict
        """
        self._require_loaded()
        session = self.sm.get_or_raise(session_id)
        session.topic = new_topic
        session.add_topic(new_topic)
        if new_difficulty:
            session.update_difficulty(new_difficulty, reason="manual_topic_switch")
        self.nlp.clear_history(session_id)
        self.kb.reset_session(session_id)
        logger.info(
            "Topic switched: %s -> %s [%s]",
            session_id[:8],
            new_topic,
            session.difficulty,
        )
        return self.sm.get_current_state(session_id)

    # ── Session Summary ────────────────────────

    def summarize_session(self, session_id):
        """
        Ask the LLM to produce a human-readable session summary.

        Returns:
            str  -- bullet-point summary text
        """
        self._require_loaded()
        session = self.sm.get_or_raise(session_id)
        return self.nlp.summarize_session(
            session_id=session_id,
            subject=session.subject,
            topic=session.topic,
        )

    def get_analytics(self, session_id):
        """
        Return live SessionAnalytics without closing the session.

        Returns:
            SessionAnalytics
        """
        self._require_loaded()
        return self.sm.get_analytics(session_id)

    def list_sessions(self, student_id=None, active_only=False):
        """List sessions, optionally filtered by student or status."""
        self._require_loaded()
        return self.sm.list_sessions(
            student_id=student_id,
            active_only=active_only,
        )

    def get_student_history(self, student_id, limit=20):
        """Return past closed session summaries for a student."""
        self._require_loaded()
        return self.sm.get_student_history(student_id, limit=limit)

    # ── Webcam Loop Integration ─────────────────

    def run_live_session(
        self,
        session_id,
        get_student_input_fn,
        display_response_fn,
        display_webcam=True,
    ):
        """
        Blocking live tutoring loop with webcam.

        Args:
            session_id           : Active session ID
            get_student_input_fn : Callable() -> str  (e.g. input() or STT)
            display_response_fn  : Callable(AgentResponse) -> None
            display_webcam       : Show annotated webcam window

        The loop runs until the student types 'quit' or 'exit',
        or until the session exceeds MAX_SESSION_DURATION_MIN.
        """
        import cv2

        self._require_loaded()
        session = self.sm.get_or_raise(session_id)

        cap = cv2.VideoCapture(emotion_cfg.WEBCAM_INDEX)
        if not cap.isOpened():
            logger.warning("Webcam not available. Running without video.")
            cap = None

        logger.info("Live session started. Type 'quit' to end.")

        try:
            while session.is_active:
                # Timeout guard
                if session.duration_minutes >= tutor_cfg.MAX_SESSION_DURATION_MIN:
                    logger.info("Session reached max duration. Closing.")
                    break

                # Grab latest frame
                frame = None
                if cap:
                    ret, frame = cap.read()
                    if not ret:
                        frame = None
                    if display_webcam and frame is not None:
                        annotated = self.detector._annotate_frame(
                            frame,
                            self.detector._last_result,
                        )
                        cv2.imshow("Emotion-Aware Tutor", annotated)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break

                # Get student input
                student_msg = get_student_input_fn()
                if not student_msg:
                    continue
                if student_msg.strip().lower() in ("quit", "exit", "bye"):
                    break

                # Process and display
                response = self.chat(
                    session_id=session_id,
                    student_message=student_msg,
                    frame=frame,
                )
                display_response_fn(response)

        finally:
            if cap:
                cap.release()
            if display_webcam:
                cv2.destroyAllWindows()

        analytics = self.end_session(session_id)
        logger.info("Live session ended. %s", analytics.summary_text())
        return analytics

    # ── Internal Helpers ───────────────────────

    def _detect_emotion(self, frame, session_id=None):
        """
        Run emotion detection on a frame.
        Returns a neutral EmotionResult if frame is None or detection fails.
        """
        if frame is not None and isinstance(frame, np.ndarray):
            self.ensure_camera()
            result = self.detector.detect_from_frame(frame, session_id=session_id)
            if result is not None:
                return result
        return self._neutral_emotion_result()

    def ensure_camera(self):
        """Load once on demand; normal studying never requires camera weights."""
        with self._camera_lock:
            if not self._camera_attempted:
                self._camera_attempted = True
                self.detector.load_model()
        return self.detector.model is not None

    def _retrieve_content(self, session_id, subject, topic, difficulty, learning_state, query):
        """Wrapper around KnowledgeBase.retrieve with error guard."""
        try:
            return self.kb.retrieve(
                subject=subject,
                topic=topic,
                difficulty=difficulty,
                learning_state=learning_state,
                query=query,
                session_id=session_id,
            )
        except Exception as exc:
            logger.error("KnowledgeBase retrieval failed: %s", exc)
            return None

    def _neutral_emotion_result(self):
        """Fallback EmotionResult used when no frame is available (camera inactive)."""
        return EmotionResult(
            emotion="neutral",
            confidence=0.0,
            learning_state="neutral",
            all_scores={},
            face=None,
            is_smoothed=False,
        )

    def _check_flashcard_suggestion(
        self, session_id: str, current_msg: str, history: list
    ) -> Optional[str]:
        """
        Scan messages to see if the student is struggling with a term/concept.
        Returns the term name if they have asked about it at least twice recently.
        """
        import re

        patterns = [r"(?:what is|what's|define|explain|what does|tell me about)\s+([^?.]+)"]

        def extract_term(text: str) -> Optional[str]:
            for pat in patterns:
                m = re.search(pat, text.lower())
                if m:
                    term = m.group(1).strip()
                    if len(term) > 2 and term not in ["that", "this", "it", "the", "a", "an"]:
                        return term
            return None

        current_term = extract_term(current_msg)
        if not current_term:
            return None

        count = 1
        for msg in history:
            if msg["role"] == "user":
                past_term = extract_term(msg["content"])
                if past_term and past_term == current_term:
                    count += 1

        if count >= 2:
            return current_term.title()

        return None

    # ── Shutdown ───────────────────────────────

    def shutdown(self):
        """Graceful shutdown: checkpoint all active sessions."""
        logger.info("TutorAgent shutting down...")
        self.sm.timeout_idle_sessions()
        self.sm.save_all_active()
        logger.info("TutorAgent shutdown complete.")


# ─────────────────────────────────────────────
# QUICK SMOKE TEST  (no LLM / webcam needed)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    agent = TutorAgent()
    # Skip full load to avoid needing API keys / model files
    # agent.load()

    print("TutorAgent class instantiated successfully.")
    print("Subsystems:")
    print("  EmotionDetector:", agent.detector)
    print("  KnowledgeBase  :", agent.kb)
    print("  NLPEngine      :", agent.nlp)
    print("  SessionManager :", agent.sm)
    print("\nCall agent.load() then agent.start_session() to begin.")
