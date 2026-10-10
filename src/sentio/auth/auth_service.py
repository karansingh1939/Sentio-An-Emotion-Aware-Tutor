import logging
import time
import uuid
from typing import Optional, Tuple

from sentio.auth.audit import AuditLogger
from sentio.auth.exceptions import CredentialsError, InvalidTokenError, ValidationError
from sentio.auth.models import RefreshToken, UserAccount
from sentio.auth.password_hasher import PBKDF2PasswordHasher
from sentio.auth.repositories import AuthRepository
from sentio.auth.token_manager import TokenManager
from sentio.auth.validators import PasswordValidator

logger = logging.getLogger(__name__)


class AuthService:
    """Orchestrates authentication, token operations, audits, and account actions."""

    def __init__(
        self,
        repo: AuthRepository,
        token_manager: TokenManager,
        hasher: Optional[PBKDF2PasswordHasher] = None,
        validator: Optional[PasswordValidator] = None,
    ):
        self.repo = repo
        self.token_manager = token_manager
        self.hasher = hasher or PBKDF2PasswordHasher()
        self.validator = validator or PasswordValidator()
        self.audit = AuditLogger(repo)

    def register_student(self, email: str, password: str) -> UserAccount:
        """Salts, hashes, and persists a new student account."""
        email_clean = email.strip().lower()
        if not email_clean or "@" not in email_clean:
            raise ValidationError("A valid email address is required.")

        # Check if email is already taken
        existing = self.repo.get_account_by_email(email_clean)
        if existing:
            raise ValidationError("An account with this email already exists.")

        # Validate password strength
        self.validator.validate(password)

        student_id = f"stu_{uuid.uuid4().hex[:12]}"
        password_hash = self.hasher.hash_password(password)

        account = UserAccount(
            student_id=student_id,
            email=email_clean,
            password_hash=password_hash,
            role="student",
            created_at=time.time(),
            consent_preferences="{}",
        )
        self.repo.save_account(account)
        self.audit.log_event(student_id, "registration", details=f"Registered email: {email_clean}")
        return account

    def login_student(
        self, email: str, password: str, ip_address: Optional[str] = None
    ) -> Tuple[str, str]:
        """Validates credentials and issues an Access + Refresh token pair."""
        email_clean = email.strip().lower()
        account = self.repo.get_account_by_email(email_clean)

        if not account:
            # Prevent user enumeration by taking similar time but raising error
            self.hasher.hash_password("dummy")
            raise CredentialsError("Invalid email or password.")

        if not self.hasher.verify_password(password, account.password_hash):
            self.audit.log_event(account.student_id, "failed_login", ip_address=ip_address)
            raise CredentialsError("Invalid email or password.")

        # Create token pair
        access_payload = {
            "sub": account.student_id,
            "email": account.email,
            "role": account.role,
            "token_type": "access",
        }
        access_token = self.token_manager.create_token(access_payload, expires_in_sec=900)  # 15 min

        refresh_id = str(uuid.uuid4())
        refresh_payload = {"sub": account.student_id, "jti": refresh_id, "token_type": "refresh"}
        refresh_token_str = self.token_manager.create_token(
            refresh_payload, expires_in_sec=2592000
        )  # 30 days

        # Save refresh token details
        refresh_token = RefreshToken(
            token_id=refresh_id,
            student_id=account.student_id,
            token=refresh_token_str,
            expires_at=time.time() + 2592000,
            created_at=time.time(),
        )
        self.repo.save_refresh_token(refresh_token)

        self.audit.log_event(account.student_id, "login", ip_address=ip_address)
        return access_token, refresh_token_str

    def refresh_access_token(self, refresh_token_str: str) -> str:
        """Rotates access token if the refresh token is valid and unrevoked."""
        # 1. Parse token
        payload = self.token_manager.verify_token(refresh_token_str)
        if payload.get("token_type") != "refresh":
            raise InvalidTokenError("A refresh token is required.")
        token_id = payload.get("jti")
        student_id = payload.get("sub")

        # 2. Check persistence
        token = self.repo.get_refresh_token(refresh_token_str)
        if (
            not token
            or token.revoked == 1
            or token.expires_at < time.time()
            or token.token_id != token_id
            or token.student_id != student_id
        ):
            raise InvalidTokenError("Refresh token is invalid or has been revoked.")

        account = self.repo.get_account_by_student_id(student_id)
        if not account:
            raise InvalidTokenError("Associated account does not exist.")

        # 3. Create fresh access token
        access_payload = {
            "sub": account.student_id,
            "email": account.email,
            "role": account.role,
            "token_type": "access",
        }
        return self.token_manager.create_token(access_payload, expires_in_sec=900)

    def logout_student(self, refresh_token_str: str):
        """Revokes a single refresh token session."""
        try:
            payload = self.token_manager.verify_token(refresh_token_str)
            if payload.get("token_type") != "refresh":
                raise InvalidTokenError("A refresh token is required.")
            token_id = payload.get("jti")
            student_id = payload.get("sub")
            self.repo.revoke_refresh_token(token_id)
            self.audit.log_event(student_id, "logout", details=f"Revoked session {token_id[:8]}")
        except Exception:
            raise InvalidTokenError("Invalid refresh token.")

    def logout_all_devices(self, student_id: str):
        """Revokes all active refresh tokens for the student ID."""
        self.repo.revoke_all_refresh_tokens(student_id)
        self.audit.log_event(student_id, "logout_all", details="Revoked all active sessions")
