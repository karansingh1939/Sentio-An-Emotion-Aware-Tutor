"""Validated HTTP request bodies."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    student_id: str = Field(..., description="Unique student identifier")
    subject: str = Field(..., description="e.g. mathematics, physics, computer_science")
    topic: str = Field(..., description="e.g. derivatives, recursion")
    difficulty: str = Field("beginner", description="beginner | intermediate | advanced")
    metadata: dict = Field(default_factory=dict, description="Optional extra fields")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="Student's text message")
    frame_b64: Optional[str] = Field(
        None, max_length=2000000, description="Base64-encoded JPEG webcam frame"
    )
    quiz_correct: Optional[bool] = Field(None, description="Was the student's quiz answer correct?")
    response_time_sec: float = Field(0.0, description="Time taken to answer quiz (seconds)")


class QuizRequest(BaseModel):
    correct: bool = Field(..., description="Was the answer correct?")
    question_preview: str = Field("", description="First 120 chars of the question")
    response_time_sec: float = Field(0.0)


class SwitchTopicRequest(BaseModel):
    topic: str = Field(..., description="New topic to study")
    difficulty: Optional[str] = Field(None, description="Override difficulty level")


class GroundingRequest(BaseModel):
    document_id: str = Field(..., description="none | all | specific document ID")


class CreateGoalRequest(BaseModel):
    goal_text: str = Field(..., description="The description of the learning goal")
    topic_id: Optional[str] = Field(None, description="Optional target topic ID")
    target_date: Optional[float] = Field(
        None, description="Optional target completion date timestamp"
    )


class QuizGenerateRequest(BaseModel):
    student_id: str = Field(..., description="Student ID")
    session_id: str = Field(..., description="Active Session ID")
    subject: str = Field(..., description="Subject")
    topic: str = Field(..., description="Topic")
    difficulty: str = Field("intermediate", description="beginner | intermediate | advanced")
    num_questions: int = Field(3, ge=1, le=20, description="Number of questions to generate")


class QuizSubmitRequest(BaseModel):
    session_id: str = Field(..., description="Active Session ID")
    answers: Dict[int, str] = Field(
        ..., description="Dictionary mapping question index to student answer"
    )


class CreateDeckRequest(BaseModel):
    student_id: str = Field(..., description="Student ID")
    deck_name: str = Field(..., description="Name of the deck")


class GenerateFlashcardsRequest(BaseModel):
    session_id: Optional[str] = None
    student_id: str = Field(..., description="Student ID")
    deck_id: str = Field(..., description="Deck ID")
    topic_id: str = Field(..., description="Topic ID")
    num_cards: int = Field(5, ge=1, le=30, description="Number of cards to generate")


class ReviewCardRequest(BaseModel):
    quality_score: int = Field(..., ge=0, le=5, description="SM-2 response quality score (0 to 5)")


class SaveWhiteboardRequest(BaseModel):
    whiteboard_id: str = Field(..., description="Whiteboard ID")
    student_id: str = Field(..., description="Student ID")
    session_id: str = Field(..., description="Active Session ID")
    title: str = Field("Tutor Drawing", description="Title of the whiteboard")
    canvas_state: Dict[str, Any] = Field(..., description="Vector shapes state dictionary")


class ExportWhiteboardRequest(BaseModel):
    format: str = Field("png", description="Export format: png | pdf")


class MermaidRequest(BaseModel):
    mermaid_code: str = Field(..., description="Mermaid flowchart code")


class TelemetryRequest(BaseModel):
    attention_score: float = Field(..., ge=0.0, le=1.0)
    focused: int = Field(..., ge=0, le=1)
    eye_openness: float = Field(..., ge=0.0, le=1.0)
    head_pose_pitch: float = Field(...)
    head_pose_yaw: float = Field(...)
    emotion: str = Field(...)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ConsentRequest(BaseModel):
    consent_version: str
    preferences: dict
