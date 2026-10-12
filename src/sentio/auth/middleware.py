import logging
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sentio.auth.exceptions import ExpiredTokenError, InvalidTokenError, PermissionDeniedError
from sentio.auth.permissions import verify_permission

logger = logging.getLogger(__name__)

# Security scheme wrapper
security_scheme = HTTPBearer(auto_error=False)


def authenticate_access_token(persister, token: str) -> Dict[str, Any]:
    """Shared HTTP/WebSocket authentication; identity comes from a live account."""
    try:
        payload = persister.token_manager.verify_token(token)
        if payload.get("token_type") != "access" or not payload.get("sub"):
            raise InvalidTokenError("An access token is required.")
        account = persister.auth_repo.get_account_by_student_id(payload["sub"])
        if account is None:
            raise InvalidTokenError("Associated account does not exist.")
        if payload.get("version", 0) != account.token_version:
            raise InvalidTokenError("Session ended after a password change. Sign in again.")
        return {"student_id": account.student_id, "email": account.email, "role": account.role}
    except ExpiredTokenError:
        raise HTTPException(status_code=401, detail="Token has expired.")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid access token.")


async def get_current_user(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict[str, Any]:
    """Require authentication. Tests may explicitly override this dependency."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header is required.")
    return authenticate_access_token(request.app.state.agent.sm.persister, credentials.credentials)


class RoleRequired:
    """Dependency filter to enforce role authorization boundaries."""

    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        role = user.get("role", "student")
        try:
            verify_permission(role, self.required_permission)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return user
