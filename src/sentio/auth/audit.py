import logging
import time
from typing import Any, Optional

from sentio.auth.models import AuditLog

logger = logging.getLogger(__name__)


class AuditLogger:
    """Writes structured security and consent event records to SQLite and runtime logs."""

    def __init__(self, repo: Any):
        self.repo = repo

    def log_event(
        self,
        student_id: str,
        event_type: str,
        ip_address: Optional[str] = None,
        details: Optional[str] = None,
    ):
        """Saves a structured log item to persistence."""
        audit = AuditLog(
            student_id=student_id,
            event_type=event_type,
            ip_address=ip_address,
            timestamp=time.time(),
            details=details,
        )
        try:
            self.repo.save_audit_log(audit)
            logger.info(f"AuditLog [{event_type}] saved for student {student_id[:8]}...")
        except Exception as exc:
            logger.error(f"Failed to save audit log: {exc}")
