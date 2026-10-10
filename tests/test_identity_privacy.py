import time
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import text

from sentio.api.app import PREFIX, agent, app
from sentio.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    PermissionDeniedError,
    ValidationError,
)
from sentio.auth.password_hasher import PBKDF2PasswordHasher
from sentio.auth.permissions import verify_permission
from sentio.auth.token_manager import TokenManager
from sentio.auth.validators import PasswordValidator
from sentio.config import api_cfg


class TestIdentityAndPrivacyPlatform(unittest.TestCase):
    def setUp(self):
        # Initialize hasher, validator, and token manager
        self.hasher = PBKDF2PasswordHasher(iterations=1000)  # Fast iterations for testing speed
        self.validator = PasswordValidator()
        self.token_manager = TokenManager(secret_key="test_secret_12345!")

        # Enable auth enforcement temporarily for specific token authorization tests
        self.original_enforce = getattr(api_cfg, "ENFORCE_AUTH", False)

    def tearDown(self):
        # Reset auth enforcement
        api_cfg.ENFORCE_AUTH = self.original_enforce

    def test_password_hashing_and_verification(self):
        """Verify PBKDF2 salts, hashes, and performs constant-time password matching."""
        pwd = "SecurePassword123!"
        hashed = self.hasher.hash_password(pwd)
        self.assertTrue(hashed.startswith("0") or len(hashed.split("$")) == 2)

        # Verify match
        self.assertTrue(self.hasher.verify_password(pwd, hashed))
        # Verify failure
        self.assertFalse(self.hasher.verify_password("WrongPassword123!", hashed))

    def test_password_complexity_validator(self):
        """Verify password validator enforces length, uppercase, digit, and special character rules."""
        # 1. Too short
        with self.assertRaises(ValidationError):
            self.validator.validate("Ab1!")
        # 2. No uppercase
        with self.assertRaises(ValidationError):
            self.validator.validate("secure123!")
        # 3. No special character
        with self.assertRaises(ValidationError):
            self.validator.validate("SecurePassword123")

    def test_token_serialization_tampering_and_expiration(self):
        """Verify TokenManager signature validation rejects tampered strings and expired payloads."""
        payload = {"sub": "stu_test_user_001", "role": "student"}
        token = self.token_manager.create_token(payload, expires_in_sec=10)

        # Parse valid token
        decoded = self.token_manager.verify_token(token)
        self.assertEqual(decoded["sub"], "stu_test_user_001")

        # Tamper signature block
        tampered_token = token[:-4] + "abcd"
        with self.assertRaises(InvalidTokenError):
            self.token_manager.verify_token(tampered_token)

        # Check expired token
        expired_token = self.token_manager.create_token(payload, expires_in_sec=-10)
        with self.assertRaises(ExpiredTokenError):
            self.token_manager.verify_token(expired_token)

    def test_role_based_permissions(self):
        """Verify permissions maps allow correct actions and deny privilege escalations."""
        # Student permissions
        verify_permission("student", "chat_tutoring")

        # Deny student admin actions
        with self.assertRaises(PermissionDeniedError):
            verify_permission("student", "manage_users")

        # Admin access
        verify_permission("admin", "manage_users")

    def test_api_registration_login_refresh_rotation_and_logout(self):
        """Verify full authentication lifecycle: register, login, refresh rotation, and session logout."""
        with TestClient(app) as client:
            email = f"student_{int(time.time())}@sentio.edu"
            pwd = "StrongPassword123!"

            # 1. Register
            reg_resp = client.post(
                f"{PREFIX}/auth/register", json={"email": email, "password": pwd}
            )
            self.assertEqual(reg_resp.status_code, 201)
            reg_data = reg_resp.json()
            reg_data["student_id"]
            self.assertEqual(reg_data["email"], email)

            # 2. Login
            login_resp = client.post(f"{PREFIX}/auth/login", json={"email": email, "password": pwd})
            self.assertEqual(login_resp.status_code, 200)
            login_data = login_resp.json()
            access_token = login_data["access_token"]
            refresh_token = login_data["refresh_token"]

            # 3. Rotate access token via refresh token
            refresh_resp = client.post(
                f"{PREFIX}/auth/refresh", json={"refresh_token": refresh_token}
            )
            self.assertEqual(refresh_resp.status_code, 200)
            new_access_token = refresh_resp.json()["access_token"]
            self.assertNotEqual(access_token, new_access_token)

            # 4. Logout (revokes token)
            logout_resp = client.post(
                f"{PREFIX}/auth/logout", json={"refresh_token": refresh_token}
            )
            self.assertEqual(logout_resp.status_code, 200)

            # 5. Verify revoked token rejects rotation attempts
            fail_resp = client.post(f"{PREFIX}/auth/refresh", json={"refresh_token": refresh_token})
            self.assertEqual(fail_resp.status_code, 401)

    def test_privacy_lifecycle_data_export_telemetry_purge_and_consent(self):
        """Verify GDPR privacy compliance operations: export, telemetry deletion, and account deletion cascade."""
        with TestClient(app) as client:
            email = f"privacy_{int(time.time())}@sentio.edu"
            pwd = "StrongPassword123!"

            # Register
            reg_resp = client.post(
                f"{PREFIX}/auth/register", json={"email": email, "password": pwd}
            )
            self.assertEqual(reg_resp.status_code, 201)
            student_id = reg_resp.json()["student_id"]

            login = client.post(f"{PREFIX}/auth/login", json={"email": email, "password": pwd})
            self.assertEqual(login.status_code, 200)
            client.headers["Authorization"] = "Bearer " + login.json()["access_token"]

            # 1. Update Consent Preferences
            consent_resp = client.post(
                f"{PREFIX}/student/{student_id}/consent",
                json={
                    "consent_version": "1.0",
                    "preferences": {"marketing": False, "telemetry": True},
                },
            )
            self.assertEqual(consent_resp.status_code, 200)

            # 2. Get Consent History
            get_consent = client.get(f"{PREFIX}/student/{student_id}/consent")
            self.assertEqual(get_consent.status_code, 200)
            self.assertTrue(len(get_consent.json()["history"]) > 0)

            # 3. Export Data
            export_resp = client.get(f"{PREFIX}/student/{student_id}/export")
            self.assertEqual(export_resp.status_code, 200)
            export_data = export_resp.json()
            self.assertEqual(export_data["student_id"], student_id)
            self.assertIn("account", export_data["data"])
            self.assertIn("consent_history", export_data["data"])

            # 4. Telemetry Purge
            telemetry_resp = client.delete(f"{PREFIX}/student/{student_id}/telemetry")
            self.assertEqual(telemetry_resp.status_code, 200)

            # 5. Account Deletion Cascade
            delete_resp = client.delete(f"{PREFIX}/student/{student_id}/data")
            self.assertEqual(delete_resp.status_code, 200)

            # Verify account record is completely gone
            with agent.sm.persister._engine.connect() as conn:
                res = conn.execute(
                    text("SELECT student_id FROM student_accounts WHERE student_id = :sid"),
                    {"sid": student_id},
                ).fetchone()
                self.assertIsNone(res)
