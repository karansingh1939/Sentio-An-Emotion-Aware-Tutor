import logging
import os
import time
from typing import Any, Dict, List, Optional, TypedDict

import psutil
from langgraph.graph import END, StateGraph

from sentio.ai.streaming import TutorPayload, output_schema
from sentio.config import tutor_cfg
from sentio.jobs.control import checkpoint, current_control
from sentio.tutor.difficulty import asks_for_another_explanation, requested_change, step

logger = logging.getLogger(__name__)


# State definition conforming to LangGraph
class OrchestratorState(TypedDict):
    session_id: str
    student_id: str
    subject: str
    topic: str
    difficulty: str
    difficulty_reason: Optional[str]
    learning_state: str
    strategy: str
    user_message: str
    document_id: Optional[str]
    slide: Optional[int]  # The slide explained this turn, in slide study.

    # Context
    student_memory: str
    retrieved_content: Optional[Any]
    tone_instruction: str

    # Flow & output
    history: List[Dict[str, str]]
    next_agent: str
    agent_response: Optional[Any]  # Holds TutorResponse

    # Observability metrics
    agent_timeline: List[Dict[str, Any]]
    selected_route: List[str]
    memory_usage_kb: float
    retrieval_latency_ms: float
    llm_latency_ms: float
    total_latency_ms: float


class SentioOrchestrator:
    def __init__(self, tutor_agent):
        self.tutor_agent = tutor_agent
        self.graph = self._compile_graph()

    def _compile_graph(self):
        """memory_lookup -> retrieve -> (refuse | generate) -> END.

        Every turn reads learner memory and retrieves evidence first. When the selected
        notes do not support the question, the graph refuses without calling the model.
        """
        workflow = StateGraph(OrchestratorState)
        workflow.add_node("memory_lookup", self.memory_lookup_node)
        workflow.add_node("retrieve", self.retrieve_node)
        workflow.add_node("refuse", self.refuse_node)
        workflow.add_node("generate", self.generate_node)

        workflow.set_entry_point("memory_lookup")
        workflow.add_edge("memory_lookup", "retrieve")
        workflow.add_conditional_edges(
            "retrieve", self.route_after_retrieval, {"refuse": "refuse", "generate": "generate"}
        )
        workflow.add_edge("refuse", END)
        workflow.add_edge("generate", END)
        return workflow.compile()

    # ── Nodes Implementation ───────────────────

    def _session_goal(self, student_id, session_id):
        from sentio.repositories.planning import active_goal

        sm = self.tutor_agent.sm
        # Goal context is optional; lightweight managers without sessions skip it.
        session = sm.get_session(session_id) if hasattr(sm, "get_session") else None
        if session is None or not session.metadata.get("goal_id"):
            return None
        with sm.persister._engine.connect() as connection:
            return active_goal(connection, student_id, session.metadata["goal_id"])

    def memory_lookup_node(self, state: OrchestratorState) -> OrchestratorState:
        t0 = time.perf_counter()

        student_id = state["student_id"]
        session_id = state["session_id"]

        # 1. Retrieve standard student history and memory context
        memory_context = self.tutor_agent.sm.get_student_memory_context(student_id)
        goal = self._session_goal(student_id, session_id)
        if goal:
            memory_context += f"\nGoal for this study session: {goal['goal_text']}"

        # 2. Retrieve telemetry summary for the current session
        attention_summary = self.tutor_agent.sm.get_attention_summary(session_id)

        # 3. Always calculate attention state and inject concise summary if records exist
        if attention_summary and attention_summary.get("count", 0) > 0:
            focus_rate = attention_summary.get("focus_rate", 1.0)
            avg_attention = attention_summary.get("avg_attention", 1.0)
            recent_state = attention_summary.get("recent_state", "focused")

            # Deterministic threshold-based attention state calculation (E6C)
            if focus_rate < 0.50 or recent_state == "distracted":
                attention_state = "DISTRACTED"
            elif avg_attention < 0.65:
                attention_state = "LOW_ENGAGEMENT"
            else:
                attention_state = "FOCUSED"

            telemetry_context = (
                f"\nStudent attention summary:\n"
                f"Focus rate {focus_rate:.0%}.\n"
                f"Recent state: {recent_state}.\n"
            )

            # Hook for adaptive tutoring rules (E6C feature-gated)
            if tutor_cfg.ENABLE_ADAPTIVE_TUTORING:
                adaptive_directives = ""
                if attention_state == "DISTRACTED":
                    adaptive_directives = (
                        "INSTRUCTION (Student is DISTRACTED):\n"
                        "- Provide significantly shorter explanations.\n"
                        "- Use simpler, more direct wording."
                    )
                elif attention_state == "LOW_ENGAGEMENT":
                    adaptive_directives = (
                        "INSTRUCTION (Student has LOW ENGAGEMENT):\n"
                        "- Break explanations into smaller, bite-sized chunks.\n"
                        "- Encourage active student interaction (e.g. ask them to explain in their own words).\n"
                        "- Suggest reviewing flashcard decks to reinforce concepts."
                    )
                elif attention_state == "FOCUSED":
                    adaptive_directives = (
                        "INSTRUCTION (Student is FOCUSED):\n"
                        "- Continue with normal tutoring pacing and explanation depth."
                    )

                if adaptive_directives:
                    telemetry_context += f"\n{adaptive_directives}\n"

            memory_context += "\n" + telemetry_context
            logger.info(
                f"MemoryLookup telemetry summary injected (adaptive={tutor_cfg.ENABLE_ADAPTIVE_TUTORING}): focus={focus_rate:.2%} state={attention_state}"
            )
        else:
            logger.info(
                f"MemoryLookup: No telemetry records found yet for session {session_id[:8]}."
            )

        # 4. Check explicit student adaptation requests (Phase 6 & 8)
        new_strategy, new_difficulty, new_learning_state, text_directive, difficulty_reason = (
            self._detect_student_adaptation_intent(
                user_msg=state["user_message"],
                current_difficulty=state["difficulty"],
                current_strategy=state["strategy"],
                current_state=state["learning_state"],
                session_id=session_id,
            )
        )
        if text_directive:
            memory_context += f"\n\n{text_directive}\n"

        # 5. Connect AdaptationEngine to evaluate student mastery and pace (Phase 7)
        if hasattr(self.tutor_agent, "intelligence") and self.tutor_agent.intelligence:
            try:
                learner_model = self.tutor_agent.intelligence.build_learner_model(student_id)
                adaptation = self.tutor_agent.intelligence.adaptation_engine.compute_adaptation(
                    topic_id=state["topic"], learner_model=learner_model
                )
                if adaptation:
                    depth = adaptation.get("depth", "standard")
                    pace = adaptation.get("pace", "standard")
                    hints_enabled = adaptation.get("hints_enabled", True)
                    adaptation_msg = f"Learner Model Adaptation: depth={depth}, pace={pace}, hints_enabled={hints_enabled}."
                    memory_context += f"\n{adaptation_msg}\n"
            except Exception as e:
                logger.debug(f"AdaptationEngine lookup skipped: {e}")

        t1 = time.perf_counter()
        latency = (t1 - t0) * 1000

        timeline = list(state.get("agent_timeline", []))
        timeline.append(
            {"agent": "memory_lookup", "start_time": t0, "end_time": t1, "latency_ms": latency}
        )

        route = list(state.get("selected_route", []))
        route.append("memory_lookup")

        return {
            **state,
            "strategy": new_strategy,
            "difficulty": new_difficulty,
            "difficulty_reason": difficulty_reason,
            "learning_state": new_learning_state,
            "student_memory": memory_context,
            "agent_timeline": timeline,
            "selected_route": route,
            "retrieval_latency_ms": state.get("retrieval_latency_ms", 0.0) + latency,
        }

    def _detect_student_adaptation_intent(
        self,
        user_msg: str,
        current_difficulty: str,
        current_strategy: str,
        current_state: str,
        session_id: str,
    ) -> tuple[str, str, str, Optional[str], Optional[str]]:
        """
        Deterministic, lightweight analysis of explicit student requests for:
        - difficulty adjustment (harder, easier)
        - pedagogical style adjustment (simplify, reframe, challenge, quiz)
        Returns (new_strategy, new_difficulty, new_learning_state, directive_instruction,
        difficulty_change_reason)
        """
        msg = user_msg.lower().strip()
        new_strategy = current_strategy
        new_difficulty = current_difficulty
        new_state = current_state
        directive = None

        # Difficulty moves only on an explicit request (see sentio.tutor.difficulty).
        direction = requested_change(msg)
        if direction:
            harder = direction == "harder"
            new_strategy = "challenge" if harder else "simplify"
            new_state = "engaged" if harder else "struggling"
            new_difficulty = step(current_difficulty, direction)
            reason = "request_harder" if harder else "request_easier"
            directive = (
                "INSTRUCTION (Student requested harder challenge):\n- Present a deeper, more advanced conceptual example.\n- Ask a thought-provoking challenge question."
                if harder
                else "INSTRUCTION (Student requested simpler explanation):\n- Strip away jargon and present an elementary, intuitive example.\n- Focus only on core fundamentals."
            )
            try:
                session = self.tutor_agent.sm.get_session(session_id)
                if session and not getattr(current_control(), "defer_turn", False):
                    session.metadata["strategy"] = new_strategy
                    session.metadata["learning_state"] = new_state
                    session.metadata["difficulty_pinned"] = False
                    session.update_difficulty(new_difficulty, reason)
            except Exception:
                pass
            return new_strategy, new_difficulty, new_state, directive, reason

        # Confusion changes the explanation and tone, not the level.
        if asks_for_another_explanation(msg):
            new_strategy = "reframe"
            new_state = "struggling"
            directive = "INSTRUCTION (Student expressed confusion):\n- Reframe the concept using an entirely different, vivid real-world analogy.\n- Break down the mechanism step by step with clear intuition."
            try:
                session = self.tutor_agent.sm.get_session(session_id)
                if session and not getattr(current_control(), "defer_turn", False):
                    session.metadata["strategy"] = new_strategy
                    session.metadata["learning_state"] = new_state
            except Exception:
                pass
            return new_strategy, new_difficulty, new_state, directive, None

        # 4. Check for quiz request
        quiz_signals = [
            "quiz me",
            "test me",
            "give me a quiz",
            "test my knowledge",
            "ask me a question",
        ]
        if any(sig in msg for sig in quiz_signals):
            directive = "INSTRUCTION (Student requested a quiz):\n- Conclude your explanation with a specific multiple-choice or short-answer comprehension check."
            return new_strategy, new_difficulty, new_state, directive, None

        return new_strategy, new_difficulty, new_state, None, None

    def route_after_retrieval(self, state: OrchestratorState) -> str:
        outcome = getattr(state.get("retrieved_content"), "evidence_outcome", "general")
        return "refuse" if outcome in ("insufficient", "no_source") else "generate"

    def _session(self, session_id):
        sm = getattr(self.tutor_agent, "sm", None)
        # Lightweight managers without sessions have no slide or camera context.
        return sm.get_session(session_id) if hasattr(sm, "get_session") else None

    def _study_slide(self, state):
        """The slide being studied in slide mode, or None to retrieve as usual."""
        from sentio.repositories.slides import SlideRepository

        session = self._session(state["session_id"])
        metadata = getattr(session, "metadata", None) or {}
        number, document_id = metadata.get("slide"), state.get("document_id")
        # Slide study needs one lecture; booleans are not slide numbers.
        if metadata.get("mode") != "slides" or type(number) is not int:
            return None
        if not isinstance(document_id, str):
            return None
        engine = self.tutor_agent.sm.persister._engine
        return SlideRepository(engine).slide(state["student_id"], document_id, number)

    def _retrieve(self, state, document_id):
        return self.tutor_agent.kb.retrieve(
            subject=state["subject"],
            topic=state["topic"],
            difficulty=state["difficulty"],
            learning_state=state["learning_state"],
            query=state["user_message"],
            session_id=state["session_id"],
            student_id=state.get("student_id"),
            document_id=document_id,
        )

    def _tone_state(self, state):
        """The camera's study mood sets the tone while fresh; it never changes anything else."""
        from sentio.emotion.policy import study_mood

        timeline = getattr(self._session(state["session_id"]), "emotion_timeline", None)
        if timeline is not None:
            mood = study_mood(timeline.recent(len(timeline)), time.time())
            if mood["fresh"]:
                return mood["learning_state"]
        return state["learning_state"]

    def retrieve_node(self, state: OrchestratorState) -> OrchestratorState:
        t0 = time.perf_counter()

        slide = self._study_slide(state)
        if slide:
            from sentio.tutor.slides import slide_content

            # The slide leads; passages from the same lecture answer follow-up questions.
            nearby = self._retrieve(state, slide["document_id"])
            content = slide_content(
                self.tutor_agent.kb,
                state["subject"],
                state["topic"],
                state["difficulty"],
                slide,
                getattr(nearby, "source_citations", None) or [],
            )
        else:
            content = self._retrieve(state, state.get("document_id"))
        control = current_control()
        citations = getattr(content, "source_citations", None) or []
        if control and control.emit and citations:
            # Streaming clients show the passages while the model is still writing.
            control.emit("sources", {"sources": citations[:5]})
        tone = self.tutor_agent.kb.get_tone_instruction(self._tone_state(state))

        t1 = time.perf_counter()
        latency = (t1 - t0) * 1000

        timeline = list(state["agent_timeline"])
        timeline.append(
            {"agent": "retrieve", "start_time": t0, "end_time": t1, "latency_ms": latency}
        )

        route = list(state["selected_route"])
        route.append("retrieve")

        return {
            **state,
            "retrieved_content": content,
            "slide": slide["number"] if slide else None,
            "tone_instruction": tone,
            "agent_timeline": timeline,
            "selected_route": route,
            "retrieval_latency_ms": state.get("retrieval_latency_ms", 0.0) + latency,
        }

    def refuse_node(self, state: OrchestratorState) -> OrchestratorState:
        """The selected notes do not support the question: answer without the model."""
        from sentio.ai.grounding import MISSING_EVIDENCE, NO_SOURCE
        from sentio.ai.models import TutorResponse

        checkpoint("insufficient selected evidence")
        outcome = getattr(state.get("retrieved_content"), "evidence_outcome", "")
        response = TutorResponse(
            text=NO_SOURCE if outcome == "no_source" else MISSING_EVIDENCE,
            strategy_used=state["strategy"],
            learning_state=state["learning_state"],
            backend_used="evidence_gate",
        )
        return {
            **state,
            "agent_response": response,
            "llm_latency_ms": 0,
            "selected_route": [*state["selected_route"], "refuse"],
        }

    def generate_node(self, state: OrchestratorState) -> OrchestratorState:
        """Generate a schema-checked answer, validate citations, or fall back to excerpts."""
        t0 = time.perf_counter()

        from sentio.ai.grounding import validate_references
        from sentio.ai.models import TutorResponse

        tone = state.get("tone_instruction", "Be encouraging.")
        system_prompt, user_message = self.tutor_agent.nlp.prompt_builder.build_study_messages(
            student_message=state["user_message"],
            subject=state["subject"],
            topic=state["topic"],
            difficulty=state["difficulty"],
            learning_state=state["learning_state"],
            strategy=state["strategy"],
            tone_instruction=tone,
            retrieved_content=state["retrieved_content"],
            student_memory=state["student_memory"],
        )
        if state.get("slide") is not None:
            from sentio.tutor.slides import SLIDE_INSTRUCTION

            system_prompt += SLIDE_INSTRUCTION

        from sentio.ai.source_practice import source_excerpt
        from sentio.shared.exceptions import LLMServiceUnavailableError

        try:
            checkpoint("generating tutor response")
            with output_schema(TutorPayload):
                raw_text, tokens = self.tutor_agent.nlp._backend.complete(
                    system_prompt=system_prompt,
                    history=state["history"],
                    user_message=user_message,
                    max_tokens=1024,
                    temperature=0.0,
                )
            TutorPayload.model_validate_json(raw_text)

            t1 = time.perf_counter()
            latency = (t1 - t0) * 1000

            tutor_resp = self.tutor_agent.nlp.parser.parse(
                raw=raw_text,
                strategy=state["strategy"],
                learning_state=state["learning_state"],
                tokens=tokens,
                latency_ms=latency,
                backend_name=self.tutor_agent.nlp._backend.name,
            )
            validate_references(tutor_resp.text, state.get("retrieved_content"))
        except (ValueError, LLMServiceUnavailableError):
            content = state.get("retrieved_content")
            if not getattr(content, "is_rag", False):
                raise
            checkpoint("showing source passages")
            t1 = time.perf_counter()
            latency = (t1 - t0) * 1000
            tutor_resp = TutorResponse(
                text=source_excerpt(content),
                strategy_used=state["strategy"],
                learning_state=state["learning_state"],
                backend_used="source_excerpt",
                latency_ms=latency,
            )
            validate_references(tutor_resp.text, content)

        timeline = list(state["agent_timeline"])
        timeline.append(
            {"agent": "generate", "start_time": t0, "end_time": t1, "latency_ms": latency}
        )

        route = list(state["selected_route"])
        route.append("generate")

        return {
            **state,
            "agent_response": tutor_resp,
            "agent_timeline": timeline,
            "selected_route": route,
            "llm_latency_ms": latency,
        }

    # ── Execute ───────────────────────────────

    def execute(self, initial_state: OrchestratorState) -> OrchestratorState:
        t_start = time.perf_counter()

        final_state = self.graph.invoke(initial_state)

        t_end = time.perf_counter()
        total_ms = (t_end - t_start) * 1000

        try:
            process = psutil.Process(os.getpid())
            mem_kb = process.memory_info().rss / 1024.0
        except Exception:
            mem_kb = 0.0

        final_state["memory_usage_kb"] = mem_kb
        final_state["total_latency_ms"] = total_ms

        return final_state
