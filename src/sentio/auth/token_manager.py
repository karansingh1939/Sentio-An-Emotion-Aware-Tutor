import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict

from sentio.auth.exceptions import ExpiredTokenError, InvalidTokenError


class TokenManager:
    """
    Manages custom secure, signed tokens using Python's standard library.
    Encapsulates serialization, deserialization, and validation.
    """

    def __init__(self, secret_key: str, issuer: str = "sentio"):
        self.secret_key = secret_key.encode("utf-8")
        self.issuer = issuer

    def _base64_url_encode(self, data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    def _base64_url_decode(self, data: str) -> bytes:
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        return base64.urlsafe_b64decode(data.encode("utf-8"))

    def create_token(self, payload: Dict[str, Any], expires_in_sec: int) -> str:
        """Serializes and signs a custom token."""
        header = {"alg": "HS256", "typ": "SEN"}

        full_payload = dict(payload)
        full_payload["iss"] = self.issuer
        full_payload["exp"] = time.time() + expires_in_sec

        header_b64 = self._base64_url_encode(json.dumps(header).encode("utf-8"))
        payload_b64 = self._base64_url_encode(json.dumps(full_payload).encode("utf-8"))

        message = f"{header_b64}.{payload_b64}"
        signature = hmac.new(self.secret_key, message.encode("utf-8"), hashlib.sha256).hexdigest()

        return f"{message}.{signature}"

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Validates token structure, signature, and expiration."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise InvalidTokenError("Malformed token structure.")

            header_b64, payload_b64, signature = parts
            message = f"{header_b64}.{payload_b64}"

            # Compute target signature
            expected_signature = hmac.new(
                self.secret_key, message.encode("utf-8"), hashlib.sha256
            ).hexdigest()

            # Constant-time comparison
            if not hmac.compare_digest(signature, expected_signature):
                raise InvalidTokenError("Invalid token signature.")

            payload_json = self._base64_url_decode(payload_b64)
            payload = json.loads(payload_json.decode("utf-8"))

            if payload.get("iss") != self.issuer:
                raise InvalidTokenError("Invalid token issuer.")

            # Check expiration
            if payload.get("exp", 0) < time.time():
                raise ExpiredTokenError("Token has expired.")

            return payload

        except (ExpiredTokenError, InvalidTokenError):
            raise
        except Exception as exc:
            raise InvalidTokenError(f"Token parsing failed: {exc}")
