"""Auth API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from sentio.api.dependencies import PREFIX, agent
from sentio.api.schemas import (
    LoginRequest,
    RecoveryKeyRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from sentio.auth.exceptions import CredentialsError, InvalidTokenError, ValidationError
from sentio.auth.middleware import get_current_user
from sentio.auth.recovery import RecoveryRepository

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(PREFIX + "/auth/register", tags=["Identity"], status_code=201)
def register_user(req: RegisterRequest):
    """
    Register a new student account.
    """
    try:
        account = agent.sm.persister.auth_service.register_student(req.email, req.password)
        recovery_key = RecoveryRepository(agent.sm.persister._engine).issue(
            account.student_id, account.password_hash
        )
        return {
            "student_id": account.student_id,
            "email": account.email,
            "role": account.role,
            "created_at": account.created_at,
            "recovery_key": recovery_key,
        }
    except ValidationError as e:
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
    except CredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post(PREFIX + "/auth/refresh", tags=["Identity"])
def refresh_token(req: RefreshRequest):
    """
    Obtain a fresh access token using a valid refresh token.
    """
    try:
        new_access_token = agent.sm.persister.auth_service.refresh_access_token(req.refresh_token)
        return {"access_token": new_access_token, "token_type": "bearer"}
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post(PREFIX + "/auth/logout", tags=["Identity"])
def logout_user(req: RefreshRequest):
    """
    Log out by revoking the specific refresh token.
    """
    try:
        agent.sm.persister.auth_service.logout_student(req.refresh_token)
        return {"logged_out": True}
    except InvalidTokenError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(PREFIX + "/auth/reset-password", tags=["Identity"])
def reset_password(req: ResetPasswordRequest, request: Request):
    service = agent.sm.persister.auth_service
    try:
        service.validator.validate(req.new_password)
        password_hash = service.hasher.hash_password(req.new_password)
        owner, key = RecoveryRepository(agent.sm.persister._engine).reset(
            req.email.strip().lower(), req.recovery_key, password_hash
        )
        jobs = getattr(request.app.state, "jobs", None)
        if jobs and not jobs.closed:
            try:
                jobs.cancel_owner(owner)
            except Exception as exc:
                logger.error(
                    "Password recovery succeeded; pending work cancellation failed (%s)",
                    type(exc).__name__,
                )
            finally:
                jobs.resume_owner(owner)
        return {"reset": True, "recovery_key": key}
    except CredentialsError as exc:
        raise HTTPException(401, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post(PREFIX + "/auth/recovery-key", tags=["Identity"])
def replace_recovery_key(req: RecoveryKeyRequest, user: dict = Depends(get_current_user)):
    service = agent.sm.persister.auth_service
    account = service.repo.get_account_by_student_id(user["student_id"])
    if account is None or not service.hasher.verify_password(
        req.current_password, account.password_hash
    ):
        raise HTTPException(400, "Current password is incorrect.")
    try:
        key = RecoveryRepository(agent.sm.persister._engine).issue(
            account.student_id, account.password_hash
        )
        return {"recovery_key": key}
    except CredentialsError as exc:
        raise HTTPException(409, str(exc)) from exc
