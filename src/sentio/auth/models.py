from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserAccount:
    """Represents a student identity account."""

    student_id: str
    email: str
    password_hash: str
    role: str = "student"
    created_at: float = field(default_factory=float)
    consent_preferences: Optional[str] = None


@dataclass
class RefreshToken:
    """Represents an active session refresh token."""

    token_id: str
    student_id: str
    token: str
    expires_at: float
    created_at: float
    revoked: int = 0


@dataclass
class AuditLog:
    """Represents a structured audit trace log."""

    student_id: str
    event_type: str
    ip_address: Optional[str] = None
    timestamp: float = 0.0
    details: Optional[str] = None


@dataclass
class ConsentHistory:
    """Represents historical record of consent updates."""

    student_id: str
    consent_version: str
    preferences_json: str
    timestamp: float
