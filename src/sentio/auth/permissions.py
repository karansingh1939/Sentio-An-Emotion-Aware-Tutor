import logging
from typing import Dict, List

from sentio.auth.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)

# Role to permissions mapping configuration
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "student": [
        "view_workspace",
        "chat_tutoring",
        "take_quizzes",
        "review_flashcards",
        "export_personal_data",
        "delete_personal_data",
    ],
    "teacher": [
        "view_workspace",
        "chat_tutoring",
        "take_quizzes",
        "review_flashcards",
        "export_personal_data",
        "view_student_analytics",
    ],
    "admin": [
        "view_workspace",
        "chat_tutoring",
        "take_quizzes",
        "review_flashcards",
        "export_personal_data",
        "delete_personal_data",
        "view_student_analytics",
        "manage_users",
        "purge_system_logs",
    ],
}


def verify_permission(role: str, permission: str):
    """
    Checks if a role is authorized to perform a permission.
    Raises PermissionDeniedError if unauthorized.
    """
    allowed = ROLE_PERMISSIONS.get(role, [])
    if permission not in allowed:
        logger.warning(
            f"Access Denied: Role {role} requested unauthorized permission '{permission}'"
        )
        raise PermissionDeniedError(f"Role '{role}' is not authorized to perform '{permission}'.")
