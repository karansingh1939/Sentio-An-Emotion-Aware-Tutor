import hashlib
import hmac
import os
from abc import ABC, abstractmethod


class PasswordHasherInterface(ABC):
    """Abstraction for password hashing strategies."""

    @abstractmethod
    def hash_password(self, password: str) -> str:
        pass

    @abstractmethod
    def verify_password(self, password: str, hashed: str) -> bool:
        pass


class PBKDF2PasswordHasher(PasswordHasherInterface):
    """
    OWASP recommended password hashing using PBKDF2-HMAC-SHA256,
    random salts, 100,000+ iterations, and constant-time verification.
    """

    def __init__(self, iterations: int = 100000):
        self.iterations = iterations

    def hash_password(self, password: str) -> str:
        """Salts and hashes a plain text password."""
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.iterations)
        return f"{salt.hex()}${key.hex()}"

    def verify_password(self, password: str, hashed: str) -> bool:
        """Constant-time validation of password vs hash."""
        try:
            salt_hex, key_hex = hashed.split("$")
            salt = bytes.fromhex(salt_hex)
            target_key = bytes.fromhex(key_hex)

            computed_key = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, self.iterations
            )
            # hmac.compare_digest prevents timing attacks
            return hmac.compare_digest(computed_key, target_key)
        except Exception:
            return False
