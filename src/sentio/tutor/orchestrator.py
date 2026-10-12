import logging
import os
import time
from typing import Any, Dict, List, Optional, TypedDict

import psutil
from langgraph.graph import END, StateGraph

from sentio.ai.streaming import TutorPayload, output_schema
from sentio.config import tutor_cfg
from sentio.jobs.control import checkpoint, current_control

logger = logging.getLogger(__name__)


# State definition conforming to LangGraph
class OrchestratorState(TypedDict):
    session_id: str
    student_id: str
    subject: str
    topic: str
    difficulty: str
    learning_state: str
    strategy: str
    user_message: str
    document_id: Optional[str]

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
        workflow = StateGraph(OrchestratorState)

        # Register nodes
        workflow.add_node("memory_lookup", self.memory_lookup_node)
        workflow.add_node("research", self.research_node)
        workflow.add_node("tutor", self.tutor_node)
        workflow.add_node("quiz", self.quiz_node)
        workflow.add_node("planner", self.planner_node)
        workflow.add_node("feedback", self.feedback_node)

        # Set entry point
        workflow.set_entry_point("memory_lookup")

        # Add routing conditional edge from memory_lookup
        workflow.add_conditional_edges(
            "memory_lookup",
            self.route_after_memory,
            {
                "research": "research",
                "tutor": "tutor",
                "quiz": "quiz",
                "planner": "planner",
                "feedback": "feedback",
            },
        )

        # Map transitions to final tutor dialogue formulator
        workflow.add_edge("research", "tutor")
        workflow.add_edge("quiz", "tutor")
        workflow.add_edge("planner", "tutor")
        workflow.add_edge("feedback", "tutor")
        workflow.add_edge("tutor", END)

        return workflow.compile()

    # ── Nodes Implementation ───────────────────

    def memory_lookup_node(self, state: OrchestratorState) -> OrchestratorState:
        t0 = time.perf_counter()

        student_id = state["student_id"]
        session_id = state["session_id"]

        # 1. Retrieve standard student history and memory context
        memory_context = self.tutor_agent.sm.get_student_memory_context(student_id)

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
                        "- Use simpler, more direct wording.\n"
                        "- Suggest/offer whiteboard drawing canvas visual support to help re-focus."
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
        new_strategy, new_difficulty, new_learning_state, text_directive = (
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
                    if (
                        not text_directive
                        and adaptation.get("difficulty") == "beginner"
                        and state["difficulty"] == "intermediate"
                    ):
                        new_difficulty = "beginner"
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
    ) -> tuple[str, str, str, Optional[str]]:
        """
        Deterministic, lightweight analysis of explicit student requests for:
        - difficulty adjustment (harder, easier)
        - pedagogical style adjustment (simplify, reframe, challenge, quiz)
        Returns (new_strategy, new_difficulty, new_learning_state, directive_instruction)
        """
        msg = user_msg.lower().strip()
        new_strategy = current_strategy
        new_difficulty = current_difficulty
        new_state = current_state
        directive = None

        difficulty_levels = ["beginner", "intermediate", "advanced"]

        # 1. Check for explicit request to increase difficulty / challenge
        harder_signals = [
            "harder",
            "more difficult",
            "make this harder",
            "make it harder",
            "challenge me",
            "more advanced",
            "too easy",
            "give me a harder",
        ]
        if any(sig in msg for sig in harder_signals):
            new_strategy = "challenge"
            idx = (
                difficulty_levels.index(current_difficulty)
                if current_difficulty in difficulty_levels
                else 0
            )
            if idx < len(difficulty_levels) - 1:
                new_difficulty = difficulty_levels[idx + 1]
            new_state = "engaged"
            directive = "INSTRUCTION (Student requested harder challenge):\n- Present a deeper, more advanced conceptual example.\n- Ask a thought-provoking challenge question."
            try:
                session = self.tutor_agent.sm.get_session(session_id)
                if session and not getattr(current_control(), "defer_turn", False):
                    session.metadata["strategy"] = new_strategy
                    session.metadata["learning_state"] = new_state
                    if session.difficulty != new_difficulty:
                        session.update_difficulty(new_difficulty, "student_request_harder")
            except Exception:
                pass
            return new_strategy, new_difficulty, new_state, directive

        # 2. Check for explicit struggle, confusion, or request to explain another way
        reframe_signals = [
            "don't understand",
            "dont understand",
            "do not understand",
            "explain another way",
            "explain it another way",
            "another way",
            "explain differently",
            "confused",
            "lost",
            "makes no sense",
        ]
        if any(sig in msg for sig in reframe_signals):
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
            return new_strategy, new_difficulty, new_state, directive

        # 3. Check for explicit request to make it easier / simpler
        simpler_signals = [
            "easier",
            "too hard",
            "make it easier",
            "too complex",
            "simplify",
            "simpler",
            "give me an easier",
        ]
        if any(sig in msg for sig in simpler_signals):
            new_strategy = "simplify"
            new_state = "struggling"
            idx = (
                difficulty_levels.index(current_difficulty)
                if current_difficulty in difficulty_levels
                else 1
            )
            if idx > 0:
                new_difficulty = difficulty_levels[idx - 1]
            directive = "INSTRUCTION (Student requested simpler explanation):\n- Strip away jargon and present an elementary, intuitive example.\n- Focus only on core fundamentals."
            try:
                session = self.tutor_agent.sm.get_session(session_id)
                if session and not getattr(current_control(), "defer_turn", False):
                    session.metadata["strategy"] = new_strategy
                    session.metadata["learning_state"] = new_state
                    if session.difficulty != new_difficulty:
                        session.update_difficulty(new_difficulty, "student_request_easier")
            except Exception:
                pass
            return new_strategy, new_difficulty, new_state, directive

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
            return new_strategy, new_difficulty, new_state, directive

        return new_strategy, new_difficulty, new_state, None

    def route_after_memory(self, state: OrchestratorState) -> str:
        control = current_control()
        deferred = control and getattr(control, "defer_turn", False)
        msg = state["user_message"].lower()

        # Scalable routing logic
        if any(
            kw in msg
            for kw in [
                "explain",
                "what is",
                "why",
                "how",
                "define",
                "concept",
                "details",
                "lookup",
                "search",
            ]
        ):
            return "research"
        elif any(kw in msg for kw in ["quiz", "test", "question", "evaluate", "assess"]):
            return "research" if deferred else "quiz"
        elif any(kw in msg for kw in ["plan", "schedule", "goals", "roadmap"]):
            return "planner"
        elif any(kw in msg for kw in ["feedback", "review", "grade"]):
            return "feedback"
        else:
            return "research" if deferred else "tutor"

    def research_node(self, state: OrchestratorState) -> OrchestratorState:
        t0 = time.perf_counter()

        content = self.tutor_agent.kb.retrieve(
            subject=state["subject"],
            topic=state["topic"],
            difficulty=state["difficulty"],
            learning_state=state["learning_state"],
            query=state["user_message"],
            session_id=state["session_id"],
            student_id=state.get("student_id"),
            document_id=state.get("document_id"),
        )
        tone = self.tutor_agent.kb.get_tone_instruction(state["learning_state"])

        t1 = time.perf_counter()
        latency = (t1 - t0) * 1000

        timeline = list(state["agent_timeline"])
        timeline.append(
            {"agent": "research", "start_time": t0, "end_time": t1, "latency_ms": latency}
        )

        route = list(state["selected_route"])
        route.append("research")

        return {
            **state,
            "retrieved_content": content,
            "tone_instruction": tone,
            "agent_timeline": timeline,
            "selected_route": route,
            "retrieval_latency_ms": state.get("retrieval_latency_ms", 0.0) + latency,
        }

    def tutor_node(self, state: OrchestratorState) -> OrchestratorState:
        t0 = time.perf_counter()

        from sentio.ai.grounding import MISSING_EVIDENCE, validate_references
        from sentio.ai.models import TutorResponse

        if getattr(state.get("retrieved_content"), "evidence_outcome", "general") == "insufficient":
            checkpoint("insufficient selected evidence")
            response = TutorResponse(
                text=MISSING_EVIDENCE,
                strategy_used=state["strategy"],
                learning_state=state["learning_state"],
                backend_used="evidence_gate",
            )
            return {
                **state,
                "agent_response": response,
                "llm_latency_ms": 0,
                "selected_route": [*state["selected_route"], "insufficient_evidence"],
            }

        tone = state.get("tone_instruction", "Be encouraging.")
        system_prompt = self.tutor_agent.nlp.prompt_builder.build_system_prompt(
            subject=state["subject"],
            topic=state["topic"],
            difficulty=state["difficulty"],
            learning_state=state["learning_state"],
            strategy=state["strategy"],
            tone_instruction=tone,
            retrieved_content=state["retrieved_content"],
        )

        # Inject memory context into system instructions
        if state["student_memory"]:
            system_prompt = state["student_memory"] + "\n\n" + system_prompt

        user_message = self.tutor_agent.nlp.prompt_builder.build_user_message(
            student_message=state["user_message"],
            learning_state=state["learning_state"],
            confidence=1.0,
        )

        checkpoint("generating tutor response")
        with output_schema(TutorPayload):
            raw_text, tokens = self.tutor_agent.nlp._backend.complete(
                system_prompt=system_prompt,
                history=state["history"],
                user_message=user_message,
                max_tokens=1024,
            )
        if current_control() and getattr(current_control(), "defer_turn", False):
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

        timeline = list(state["agent_timeline"])
        timeline.append({"agent": "tutor", "start_time": t0, "end_time": t1, "latency_ms": latency})

        route = list(state["selected_route"])
        route.append("tutor")

        return {
            **state,
            "agent_response": tutor_resp,
            "agent_timeline": timeline,
            "selected_route": route,
            "llm_latency_ms": latency,
        }

    # ── Stub Nodes for Extensibility ──────────

    def quiz_node(self, state: OrchestratorState) -> OrchestratorState:
        t0 = time.perf_counter()
        logger.info("Executing real Quiz Node in LangGraph orchestrator.")

        from sentio.quiz.quiz_service import QuizService

        quiz_service = QuizService(self.tutor_agent)

        try:
            quiz = quiz_service.generate_quiz(
                student_id=state["student_id"],
                session_id=state["session_id"],
                subject=state["subject"],
                topic=state["topic"],
                difficulty=state["difficulty"],
                num_questions=3,
            )
        except Exception as e:
            logger.error(f"Quiz node generation failed: {e}")
            quiz = None

        t1 = time.perf_counter()
        latency = (t1 - t0) * 1000

        timeline = list(state["agent_timeline"])
        timeline.append({"agent": "quiz", "start_time": t0, "end_time": t1, "latency_ms": latency})
        route = list(state["selected_route"])
        route.append("quiz")

        # Inject the generated quiz markdown context into the state so the tutor node can reference it
        quiz_context = ""
        if quiz:
            quiz_context = f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nGENERATED QUIZ FOR STUDENT (Present this quiz to the student in your response text)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nQuiz ID: {quiz['quiz_id']}\nTitle: {quiz['title']}\n\n"
            for idx, q in enumerate(quiz["questions"]):
                quiz_context += f"Question {idx + 1}: ({q['question_type']}) {q['question_text']}\n"
                if q["options"]:
                    for opt in q["options"]:
                        quiz_context += f"  - {opt}\n"
                quiz_context += "\n"

        # Append quiz_context to student_memory
        updated_student_memory = state["student_memory"] or ""
        if quiz_context:
            updated_student_memory += "\n" + quiz_context

        return {
            **state,
            "student_memory": updated_student_memory,
            "agent_timeline": timeline,
            "selected_route": route,
            "retrieval_latency_ms": state.get("retrieval_latency_ms", 0.0) + latency,
        }

    def planner_node(self, state: OrchestratorState) -> OrchestratorState:
        from sentio.study.planning import PlanningService

        t0 = time.perf_counter()
        checkpoint("reading revision plan")
        plan = PlanningService(self.tutor_agent.sm.persister._engine).daily_plan(
            state["student_id"], persist=False
        )
        summary = (
            "Revision priorities from saved practice (completion is self-reported):\n"
            + "\n".join(
                f"- {task['title']} ({task['minutes']} min; {'completed' if task['completed_at'] else 'pending'})"
                for task in plan["tasks"]
            )
        )
        t1 = time.perf_counter()

        timeline = list(state["agent_timeline"])
        timeline.append(
            {
                "agent": "planner",
                "start_time": t0,
                "end_time": t1,
                "latency_ms": (t1 - t0) * 1000,
            }
        )
        route = list(state["selected_route"])
        route.append("planner")

        return {
            **state,
            "student_memory": (state["student_memory"] or "") + "\n" + summary,
            "agent_timeline": timeline,
            "selected_route": route,
        }

    def feedback_node(self, state: OrchestratorState) -> OrchestratorState:
        from sentio.study.planning import PlanningService

        t0 = time.perf_counter()
        checkpoint("reading practice evidence")
        feedback = PlanningService(self.tutor_agent.sm.persister._engine).feedback(
            state["student_id"]
        )
        summary = (
            feedback["summary"]
            + "\nRecent mistakes:\n"
            + "\n".join(
                f"- {mistake['topic']}: {mistake['question_text']}"
                for mistake in feedback["mistakes"]
            )
        )
        t1 = time.perf_counter()

        timeline = list(state["agent_timeline"])
        timeline.append(
            {
                "agent": "feedback",
                "start_time": t0,
                "end_time": t1,
                "latency_ms": (t1 - t0) * 1000,
            }
        )
        route = list(state["selected_route"])
        route.append("feedback")

        return {
            **state,
            "student_memory": (state["student_memory"] or "") + "\n" + summary,
            "agent_timeline": timeline,
            "selected_route": route,
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
