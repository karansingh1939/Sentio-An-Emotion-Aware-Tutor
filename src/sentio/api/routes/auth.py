"""Auth API routes."""

import logging

from fastapi import APIRouter, HTTPException, Request

from sentio.api.dependencies import PREFIX, agent
from sentio.api.schemas import LoginRequest, RefreshRequest, RegisterRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/auth/register", tags=["Identity"], status_code=201)
def register_user(req: RegisterRequest):
    """
    Register a new student account.
    """
    try:
        account = agent.sm.persister.auth_service.register_student(req.email, req.password)
        return {
            "student_id": account.student_id,
            "email": account.email,
            "role": account.role,
            "created_at": account.created_at,
        }
    except Exception as e:
        logger.exception("Registration failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.post(PREFIX + "/auth/login", tags=["Identity"])
def login_user(req: LoginRequest, request: Request):
    """
    Login student using email/password. Returns access and refresh token pair.
    """
    try:
        ip = request.client.host if request.client else "unknown"
        access_token, refresh_token = agent.sm.persister.auth_service.login_student(
            req.email, req.password, ip
        )
        account = agent.sm.persister.auth_service.repo.get_account_by_email(
            req.email.strip().lower()
        )
        if account is None:
            raise HTTPException(status_code=401, detail="Account no longer exists.")
        student_id = account.student_id
        email = account.email
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "student_id": student_id,
            "email": email,
            "role": account.role,
        }
    except Exception as e:
        logger.exception("Login failed")
        raise HTTPException(status_code=401, detail=str(e))


@router.post(PREFIX + "/auth/refresh", tags=["Identity"])
def refresh_token(req: RefreshRequest):
    """
    Obtain a fresh access token using a valid refresh token.
    """
    try:
        new_access_token = agent.sm.persister.auth_service.refresh_access_token(req.refresh_token)
        return {"access_token": new_access_token, "token_type": "bearer"}
    except Exception as e:
        logger.exception("Token refresh failed")
        raise HTTPException(status_code=401, detail=str(e))


@router.post(PREFIX + "/auth/logout", tags=["Identity"])
def logout_user(req: RefreshRequest):
    """
    Log out by revoking the specific refresh token.
    """
    try:
        agent.sm.persister.auth_service.logout_student(req.refresh_token)
        return {"logged_out": True}
    except Exception as e:
        logger.exception("Logout failed")
        raise HTTPException(status_code=400, detail=str(e))
