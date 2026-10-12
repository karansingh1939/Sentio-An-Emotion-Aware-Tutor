import base64
import hashlib
import hmac
import json
import math
import time
from typing import Any, Dict

import jwt

from sentio.auth.exceptions import ExpiredTokenError, InvalidTokenError


class TokenManager:
    """
    Issues standard HS256 JWTs and verifies unexpired legacy signed tokens.
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
        """Issue a standard HS256 JWT with required issuer and expiration."""
        full_payload = dict(payload)
        full_payload["iss"] = self.issuer
        full_payload["exp"] = time.time() + expires_in_sec
        full_payload["iat"] = int(time.time())
        return jwt.encode(full_payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Validates token structure, signature, and expiration."""
        try:
            if not isinstance(token, str) or len(token) > 8192:
                raise InvalidTokenError("Malformed token structure.")
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "HS256":
                raise InvalidTokenError("Unsupported token algorithm.")
            if header.get("typ") == "SEN":
                # Upgrade compatibility: old persisted sign-ins expire normally.
                parts = token.split(".")
                message = f"{parts[0]}.{parts[1]}"
                signature = hmac.new(self.secret_key, message.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(parts[2], signature):
                    raise InvalidTokenError("Invalid token signature.")
                payload = json.loads(self._base64_url_decode(parts[1]))
            elif header.get("typ") == "JWT":
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=["HS256"],
                    issuer=self.issuer,
                    options={"require": ["exp", "iss"], "verify_exp": False},
                )
            else:
                raise InvalidTokenError("Unsupported token type.")
            if not isinstance(payload, dict) or payload.get("iss") != self.issuer:
                raise InvalidTokenError("Invalid token issuer.")
            expiry = payload.get("exp")
            if type(expiry) not in (int, float) or not math.isfinite(expiry):
                raise InvalidTokenError("Token expiration is required.")
            if expiry <= time.time():
                raise ExpiredTokenError("Token has expired.")
            return payload
        except (ExpiredTokenError, InvalidTokenError):
            raise
        except Exception as exc:
            raise InvalidTokenError("Token verification failed.") from exc
