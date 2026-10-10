"""
structured_parser.py -- Structured Output Reliability Layer (Phase D0)
=======================================================================
Provides:
  - Pydantic schemas for Quiz, Flashcards, Quiz Scoring, and Whiteboards
  - 4-Attempt JSON Recovery Layer (Direct -> Repair -> Regex -> Regenerate)
  - Configurable retry/regeneration logic
  - In-memory metrics tracking for parse/recovery observability
"""

import ast
import json
import logging
import re
import threading
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel, Field, ValidationError, model_validator

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────


# --- 1. Quiz Generation ---
class QuizQuestion(BaseModel):
    question_text: str = Field(..., description="The body of the question")
    question_type: Literal["multiple_choice", "true_false", "short_answer", "fill_in_the_blank"]
    options: Optional[List[str]] = Field(
        default=None, description="List of options for multiple choice questions, else null"
    )
    correct_answer: str = Field(..., min_length=1)
    explanation: Optional[str] = Field(
        default="No explanation provided.",
        description="Step-by-step reasoning/explanation for the correct answer",
    )
    difficulty: str = Field("intermediate", description="beginner | intermediate | advanced")
    topic: Optional[str] = Field(
        default="", description="Specific educational topic or sub-concept"
    )

    @model_validator(mode="after")
    def validate_answer(self):
        if not self.question_text.strip():
            raise ValueError("Question must not be blank.")
        self.explanation = self.explanation or "No explanation provided."
        self.topic = self.topic or ""
        if not self.correct_answer.strip():
            raise ValueError("Correct answer must not be blank.")
        if self.question_type in ("multiple_choice", "true_false"):
            if (
                not self.options
                or len(self.options) < 2
                or len(set(self.options)) != len(self.options)
            ):
                raise ValueError("Choice questions require distinct options.")
            if (
                any(not option.strip() for option in self.options)
                or self.correct_answer not in self.options
            ):
                raise ValueError("Correct answer must match a nonempty option.")
        return self


class QuizPayloadSchema(BaseModel):
    title: str = Field(..., description="Name or title of the quiz")
    questions: List[QuizQuestion] = Field(
        ..., min_length=1, max_length=20, description="Array of questions"
    )


# --- 2. Quiz Scoring ---
class QuestionFeedback(BaseModel):
    question_index: int = Field(..., description="0-indexed index of the question")
    is_correct: bool = Field(..., description="Whether the student got it right")
    student_answer: str = Field(..., description="The answer provided by the student")
    correct_answer: str = Field(..., description="The correct answer key or description")
    explanation: str = Field(..., description="Detailed explanation of the answer")
    score: float = Field(..., description="Numerical score from 0.0 to 1.0")


class QuizScoringSchema(BaseModel):
    total_score: float = Field(..., description="Average score across all questions")
    passed: bool = Field(..., description="True if total_score >= 0.6, else False")
    feedback: List[QuestionFeedback] = Field(..., description="Feedback for each question")
    summary: str = Field(
        ..., description="Warm encouraging pedagogical summary of student strengths and weak areas"
    )


class ShortAnswerGrade(BaseModel):
    is_correct: bool = Field(strict=True)
    score: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def check_threshold(self):
        if self.is_correct != (self.score >= 0.6):
            raise ValueError("Correctness must agree with score threshold.")
        return self


# --- 3. Flashcard Generation ---
class FlashcardItem(BaseModel):
    front: str = Field(..., description="Concept, term, or question on front of card")
    back: str = Field(..., description="Definition, explanation, or answer on back of card")
    tags: List[str] = Field(default_factory=list, description="Keywords or topic labels")


class FlashcardPayloadSchema(BaseModel):
    deck_name: str = Field(..., description="The grouping deck topic name")
    cards: List[FlashcardItem] = Field(..., description="List of generated flashcards")


# --- 4. Whiteboard Diagram Payload ---
class WhiteboardShape(BaseModel):
    type: str = Field(..., description="rectangle | circle | line | arrow | text")
    x: float = Field(..., description="X coordinate of shape placement")
    y: float = Field(..., description="Y coordinate of shape placement")
    width: Optional[float] = Field(None, description="Width of rectangle or circle radius/diameter")
    height: Optional[float] = Field(None, description="Height of shape")
    points: Optional[List[Tuple[float, float]]] = Field(None, description="Points for lines/arrows")
    color: str = Field("black", description="Stroke color")
    text: Optional[str] = Field(None, description="Text value if type is text or label")
    fontSize: Optional[int] = Field(None, description="Font size for text label")


class WhiteboardDiagramSchema(BaseModel):
    title: str = Field("Tutor Diagram", description="Title of the whiteboard drawing")
    mermaid_code: Optional[str] = Field(
        None, description="Mermaid.js diagram string for structural renderings"
    )
    shapes: List[WhiteboardShape] = Field(default_factory=list, description="List of vector shapes")


# ─────────────────────────────────────────────
# OBSERVABILITY METRICS
# ─────────────────────────────────────────────


class ParserMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self.total_attempts = 0
        self.direct_successes = 0
        self.recovered_successes = 0
        self.regenerations = 0
        self.total_failures = 0

    def record_attempt(self):
        with self._lock:
            self.total_attempts += 1

    def record_direct_success(self):
        with self._lock:
            self.direct_successes += 1

    def record_recovered_success(self):
        with self._lock:
            self.recovered_successes += 1

    def record_regeneration(self):
        with self._lock:
            self.regenerations += 1

    def record_failure(self):
        with self._lock:
            self.total_failures += 1

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            success_count = self.direct_successes + self.recovered_successes
            attempts = max(1, self.total_attempts)
            success_rate = (success_count / attempts) * 100
            failure_rate = (self.total_failures / attempts) * 100

            recovery_div = success_count + self.total_failures
            recovery_rate = (self.recovered_successes / max(1, recovery_div)) * 100

            return {
                "total_attempts": self.total_attempts,
                "direct_successes": self.direct_successes,
                "recovered_successes": self.recovered_successes,
                "regenerations": self.regenerations,
                "total_failures": self.total_failures,
                "parse_success_rate": round(success_rate, 2),
                "parse_failure_rate": round(failure_rate, 2),
                "recovery_success_rate": round(recovery_rate, 2),
            }


metrics = ParserMetrics()


# ─────────────────────────────────────────────
# JSON REPAIR & REGEX EXTRACTORS
# ─────────────────────────────────────────────


def repair_json_string(s: str) -> str:
    """
    Cleans and completes truncated JSON strings.
    Extracts the first major block starting with { or [ and completes all unclosed structures.
    Discards trailing garbage by stopping once the root structure is fully closed.
    """
    s = s.strip()

    first_brace = s.find("{")
    first_bracket = s.find("[")

    if first_brace == -1 and first_bracket == -1:
        return s

    start_idx = (
        first_brace
        if (first_bracket == -1 or (first_brace != -1 and first_brace < first_bracket))
        else first_bracket
    )
    s = s[start_idx:]

    in_string = False
    string_char = None
    escaped = False
    stack = []

    clean_chars = []
    started = False

    i = 0
    while i < len(s):
        char = s[i]

        if escaped:
            clean_chars.append(char)
            escaped = False
            i += 1
            continue

        if char == "\\":
            clean_chars.append(char)
            escaped = True
            i += 1
            continue

        if in_string:
            if char == string_char:
                in_string = False
                string_char = None
                clean_chars.append('"')  # Match standardized opening quote
            else:
                clean_chars.append(char)
        else:
            if char in ('"', "'"):
                in_string = True
                string_char = char
                clean_chars.append('"')  # standardise to double quotes
            elif char == "{":
                stack.append("}")
                clean_chars.append(char)
                started = True
            elif char == "[":
                stack.append("]")
                clean_chars.append(char)
                started = True
            elif char == "}":
                if stack and stack[-1] == "}":
                    stack.pop()
                clean_chars.append(char)
            elif char == "]":
                if stack and stack[-1] == "]":
                    stack.pop()
                clean_chars.append(char)
            else:
                clean_chars.append(char)

        # Check if we finished the root object or array
        if started and not stack and not in_string:
            break

        i += 1

    if in_string:
        clean_chars.append('"')

    repaired = "".join(clean_chars)

    # Strip trailing commas right before closing tokens
    repaired = re.sub(r",\s*\}", "}", repaired)
    repaired = re.sub(r",\s*\]", "]", repaired)

    # Close any remaining brackets in reverse order
    while stack:
        close_char = stack.pop()
        repaired = repaired.rstrip().rstrip(",")
        repaired += close_char

    return repaired


def regex_fallback_parse(raw: str, schema_class: Type[BaseModel]) -> Dict[str, Any]:
    """
    Scrapes key-value pairs or structured fields using regex if JSON parsers fail.
    Populates dictionaries for validation.
    """
    result = {}

    if schema_class == QuizPayloadSchema:
        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', raw)
        if title_match:
            result["title"] = title_match.group(1)

        q_blocks = []
        matches = re.finditer(
            r'\{\s*"(?:question_text|question)"\s*:\s*"([^"]+)"(.*?)\}', raw, re.DOTALL
        )
        for m in matches:
            q_text = m.group(1)
            rest = m.group(2)

            q_data = {"question_text": q_text}

            q_type_m = re.search(r'"(?:question_type|type)"\s*:\s*"([^"]+)"', rest)
            if q_type_m:
                q_data["question_type"] = q_type_m.group(1)

            correct_m = re.search(r'"(?:correct_answer|answer|correct)"\s*:\s*"([^"]+)"', rest)
            if correct_m:
                q_data["correct_answer"] = correct_m.group(1)

            exp_m = re.search(r'"explanation"\s*:\s*"([^"]+)"', rest)
            if exp_m:
                q_data["explanation"] = exp_m.group(1)

            diff_m = re.search(r'"difficulty"\s*:\s*"([^"]+)"', rest)
            if diff_m:
                q_data["difficulty"] = diff_m.group(1)

            topic_m = re.search(r'"topic"\s*:\s*"([^"]+)"', rest)
            if topic_m:
                q_data["topic"] = topic_m.group(1)

            options_m = re.search(r'"options"\s*:\s*\[(.*?)\]', rest, re.DOTALL)
            if options_m:
                opt_str = options_m.group(1)
                options = [o.strip(" \"'") for o in opt_str.split(",") if o.strip()]
                q_data["options"] = options

            q_blocks.append(q_data)

        if q_blocks:
            result["questions"] = q_blocks

    elif schema_class == QuizScoringSchema:
        score_m = re.search(r'"total_score"\s*:\s*([0-9.]+)', raw)
        if score_m:
            result["total_score"] = float(score_m.group(1))

        passed_m = re.search(r'"passed"\s*:\s*(true|false)', raw, re.IGNORECASE)
        if passed_m:
            result["passed"] = passed_m.group(1).lower() == "true"

        sum_m = re.search(r'"summary"\s*:\s*"([^"]+)"', raw)
        if sum_m:
            result["summary"] = sum_m.group(1)

        fb_blocks = []
        matches = re.finditer(r'\{\s*"question_index"\s*:\s*(\d+)(.*?)\}', raw, re.DOTALL)
        for m in matches:
            idx = int(m.group(1))
            rest = m.group(2)

            fb_data = {"question_index": idx}

            correct_m = re.search(r'"is_correct"\s*:\s*(true|false)', rest, re.IGNORECASE)
            if correct_m:
                fb_data["is_correct"] = correct_m.group(1).lower() == "true"

            student_ans_m = re.search(r'"student_answer"\s*:\s*"([^"]+)"', rest)
            if student_ans_m:
                fb_data["student_answer"] = student_ans_m.group(1)

            correct_ans_m = re.search(r'"correct_answer"\s*:\s*"([^"]+)"', rest)
            if correct_ans_m:
                fb_data["correct_answer"] = correct_ans_m.group(1)

            exp_m = re.search(r'"explanation"\s*:\s*"([^"]+)"', rest)
            if exp_m:
                fb_data["explanation"] = exp_m.group(1)

            fb_score_m = re.search(r'"score"\s*:\s*([0-9.]+)', rest)
            if fb_score_m:
                fb_data["score"] = float(fb_score_m.group(1))

            fb_blocks.append(fb_data)

        if fb_blocks:
            result["feedback"] = fb_blocks

    elif schema_class == FlashcardPayloadSchema:
        deck_m = re.search(r'"deck_name"\s*:\s*"([^"]+)"', raw)
        if deck_m:
            result["deck_name"] = deck_m.group(1)

        card_blocks = []
        matches = re.finditer(r'\{\s*"front"\s*:\s*"([^"]+)"(.*?)\}', raw, re.DOTALL)
        for m in matches:
            front = m.group(1)
            rest = m.group(2)

            card_data = {"front": front}

            back_m = re.search(r'"back"\s*:\s*"([^"]+)"', rest)
            if back_m:
                card_data["back"] = back_m.group(1)

            tags_m = re.search(r'"tags"\s*:\s*\[(.*?)\]', rest)
            if tags_m:
                card_data["tags"] = [t.strip(" \"'") for t in tags_m.group(1).split(",")]

            card_blocks.append(card_data)

        if card_blocks:
            result["cards"] = card_blocks

    elif schema_class == WhiteboardDiagramSchema:
        title_m = re.search(r'"title"\s*:\s*"([^"]+)"', raw)
        if title_m:
            result["title"] = title_m.group(1)

        mermaid_m = re.search(r'"mermaid_code"\s*:\s*"([^"]+)"', raw)
        if not mermaid_m:
            mermaid_m = re.search(r'"mermaid_code"\s*:\s*"""(.*?)"""', raw, re.DOTALL)
        if not mermaid_m:
            mermaid_m = re.search(r"```mermaid\s*(.*?)\s*```", raw, re.DOTALL)
        if mermaid_m:
            result["mermaid_code"] = mermaid_m.group(1).strip()

        shapes = []
        matches = re.finditer(r'\{\s*"type"\s*:\s*"([^"]+)"(.*?)\}', raw, re.DOTALL)
        for m in matches:
            stype = m.group(1)
            rest = m.group(2)

            shape_data = {"type": stype}

            x_m = re.search(r'"x"\s*:\s*([0-9.-]+)', rest)
            y_m = re.search(r'"y"\s*:\s*([0-9.-]+)', rest)
            if x_m:
                shape_data["x"] = float(x_m.group(1))
            if y_m:
                shape_data["y"] = float(y_m.group(1))

            w_m = re.search(r'"width"\s*:\s*([0-9.-]+)', rest)
            if w_m:
                shape_data["width"] = float(w_m.group(1))

            h_m = re.search(r'"height"\s*:\s*([0-9.-]+)', rest)
            if h_m:
                shape_data["height"] = float(h_m.group(1))

            color_m = re.search(r'"color"\s*:\s*"([^"]+)"', rest)
            if color_m:
                shape_data["color"] = color_m.group(1)

            text_m = re.search(r'"text"\s*:\s*"([^"]+)"', rest)
            if text_m:
                shape_data["text"] = text_m.group(1)

            shapes.append(shape_data)

        if shapes:
            result["shapes"] = shapes

    return result


def normalize_keys(data: Any) -> Any:
    if isinstance(data, list):
        return [normalize_keys(x) for x in data]
    elif isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            norm_k = k
            if k in ["question", "questionText", "text"]:
                norm_k = "question_text"
            elif k in ["questionType", "type"]:
                norm_k = "question_type"
            elif k in ["correctAnswer", "answer", "correct"]:
                norm_k = "correct_answer"
            new_dict[norm_k] = normalize_keys(v)

        # Resilient additions for quiz questions
        if (
            "question_text" in new_dict
            or "question_type" in new_dict
            or "correct_answer" in new_dict
        ):
            if "correct_answer" in new_dict:
                val = new_dict["correct_answer"]
                if val is None:
                    new_dict["correct_answer"] = "N/A"
                elif isinstance(val, bool):
                    new_dict["correct_answer"] = "True" if val else "False"
                elif isinstance(val, (int, float)):
                    new_dict["correct_answer"] = str(val)
            else:
                new_dict["correct_answer"] = "N/A"

            if "explanation" not in new_dict or new_dict["explanation"] is None:
                new_dict["explanation"] = "No explanation provided."
            if "difficulty" not in new_dict or new_dict["difficulty"] is None:
                new_dict["difficulty"] = "intermediate"
            if "topic" not in new_dict or new_dict["topic"] is None:
                new_dict["topic"] = ""

            if "options" in new_dict and isinstance(new_dict["options"], list):
                new_dict["options"] = [
                    str(opt) if opt is not None else "" for opt in new_dict["options"]
                ]

        # Resilient additions for flashcards
        if "front" in new_dict or "back" in new_dict:
            if "front" not in new_dict or new_dict["front"] is None:
                new_dict["front"] = "N/A"
            if "back" not in new_dict or new_dict["back"] is None:
                new_dict["back"] = "N/A"
            if "tags" not in new_dict or new_dict["tags"] is None:
                new_dict["tags"] = []
            elif isinstance(new_dict["tags"], list):
                new_dict["tags"] = [str(t) for t in new_dict["tags"] if t is not None]

        return new_dict
    return data


def validate_model(schema_class: Type[T], data: Any) -> T:
    normalized_data = normalize_keys(data)
    if hasattr(schema_class, "model_validate"):
        return schema_class.model_validate(normalized_data)
    return schema_class.parse_obj(normalized_data)


# ─────────────────────────────────────────────
# CORE RELIABILITY PIPELINE
# ─────────────────────────────────────────────


def extract_json_block(s: str) -> str:
    """
    Extracts the substring between the first opening brace/bracket
    and the last closing brace/bracket to strip prefix preambles and postscripts.
    """
    s = s.strip()
    first_brace = s.find("{")
    last_brace = s.rfind("}")
    first_bracket = s.find("[")
    last_bracket = s.rfind("]")

    start = -1
    end = -1

    if first_brace != -1 and last_brace != -1:
        if first_bracket != -1 and last_bracket != -1:
            if first_brace < first_bracket:
                start = first_brace
                end = last_brace
            else:
                start = first_bracket
                end = last_bracket
        else:
            start = first_brace
            end = last_brace
    elif first_bracket != -1 and last_bracket != -1:
        start = first_bracket
        end = last_bracket

    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


def parse_structured_output(
    raw_text: str,
    schema_class: Type[T],
    llm_call_fn: Optional[
        Callable[[str, List[Dict[str, str]], str], Tuple[str, int, float]]
    ] = None,
    original_prompt_args: Optional[Dict[str, Any]] = None,
    max_regenerations: int = 2,
) -> T:
    """
    Executes the 4-Attempt JSON Recovery Layer pipeline.
    Validates output structure using Pydantic schemas.
    """
    metrics.record_attempt()
    current_text = raw_text

    last_error = None

    for attempt in range(max_regenerations + 1):
        if attempt > 0:
            metrics.record_regeneration()

        logger.info(f"Structured Parse Attempt {attempt + 1} for schema {schema_class.__name__}")

        cleaned = current_text.strip()
        if not cleaned:
            # Trigger ValidationError by validating empty dict
            try:
                validate_model(schema_class, {})
            except ValidationError as val_err:
                last_error = val_err
        else:
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Extract raw JSON boundaries to strip commentary preambles and postscripts
            extracted = extract_json_block(cleaned)

            # --- Attempt 1: Direct JSON parse ---
            try:
                parsed_dict = json.loads(extracted)
                obj = validate_model(schema_class, parsed_dict)
                if attempt == 0:
                    metrics.record_direct_success()
                else:
                    metrics.record_recovered_success()
                return obj
            except (json.JSONDecodeError, ValidationError) as e:
                logger.debug(f"Attempt 1 (Direct Parse) failed: {e}")
                last_error = e

            # --- Attempt 2: JSON repair & recovery ---
            try:
                repaired = repair_json_string(current_text)
                parsed_dict = json.loads(repaired)
                obj = validate_model(schema_class, parsed_dict)
                metrics.record_recovered_success()
                logger.info("JSON successfully parsed after Stack Repair.")
                return obj
            except (json.JSONDecodeError, ValidationError) as e:
                logger.debug(f"Attempt 2 (Stack Repair) failed: {e}")
                last_error = e

            # --- Attempt 2.5: AST Literal Eval (fixes Python-like single quotes) ---
            try:
                repaired = repair_json_string(current_text)
                parsed_dict = ast.literal_eval(repaired)
                obj = validate_model(schema_class, parsed_dict)
                metrics.record_recovered_success()
                logger.info("JSON successfully parsed after Stack Repair + AST Eval.")
                return obj
            except (SyntaxError, ValueError, ValidationError) as e:
                logger.debug(f"Attempt 2.5 (AST Eval) failed: {e}")
                last_error = e

            # --- Attempt 3: Regex-based extraction ---
            try:
                extracted_dict = regex_fallback_parse(current_text, schema_class)
                if extracted_dict:
                    obj = validate_model(schema_class, extracted_dict)
                    metrics.record_recovered_success()
                    logger.info("JSON successfully reconstructed via Regex Fallback extraction.")
                    return obj
            except Exception as e:
                logger.debug(f"Attempt 3 (Regex Fallback) failed: {e}")
                last_error = e

        # --- Attempt 4: LLM regeneration ---
        if attempt < max_regenerations and llm_call_fn and original_prompt_args:
            logger.warning(
                f"All parse fallbacks failed. Requesting LLM regeneration (attempt {attempt + 1}/{max_regenerations})."
            )

            system_prompt = original_prompt_args.get("system_prompt", "")
            history = original_prompt_args.get("history", [])
            user_message = original_prompt_args.get("user_message", "")

            retry_instruction = (
                f"\n\n[SYSTEM WARNING: Your previous response was invalid. "
                f"It failed JSON decoding or schema validation.\n"
                f"Validation Error: {last_error}.\n"
                f"Please correct the output. You MUST reply ONLY with a valid, closed JSON "
                f"object conforming to the schema. Do not truncate the JSON.]"
            )

            try:
                llm_res = llm_call_fn(system_prompt, history, user_message + retry_instruction)
                if isinstance(llm_res, tuple):
                    res_text = llm_res[0]
                else:
                    res_text = llm_res
                current_text = res_text
            except Exception as llm_err:
                logger.error(f"LLM regeneration call failed: {llm_err}")
                last_error = llm_err
                break
        else:
            break

    metrics.record_failure()
    err_msg = f"Failed to parse structured output for {schema_class.__name__} after {max_regenerations + 1} attempts."
    logger.error(err_msg)

    if last_error:
        raise last_error
    else:
        raise ValueError(err_msg)
