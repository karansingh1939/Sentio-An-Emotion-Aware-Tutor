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
    Versioned PBKDF2-HMAC-SHA256 with random salts and constant-time verification.
    """

    def __init__(self, iterations: int = 600000):
        self.iterations = iterations

    def hash_password(self, password: str) -> str:
        """Salts and hashes a plain text password."""
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.iterations)
        return f"pbkdf2_sha256${self.iterations}${salt.hex()}${key.hex()}"

    def verify_password(self, password: str, hashed: str) -> bool:
        """Constant-time validation of password vs hash."""
        try:
            parts = hashed.split("$")
            if len(parts) == 2:
                salt_hex, key_hex = parts
                iterations = 100000
            elif len(parts) == 4 and parts[0] == "pbkdf2_sha256":
                iterations = int(parts[1])
                salt_hex, key_hex = parts[2:]
            else:
                return False
            if not 1000 <= iterations <= 2000000:
                return False
            salt = bytes.fromhex(salt_hex)
            target_key = bytes.fromhex(key_hex)

            computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            # hmac.compare_digest prevents timing attacks
            return hmac.compare_digest(computed_key, target_key)
        except Exception:
            return False

    def needs_upgrade(self, hashed):
        parts = hashed.split("$")
        return len(parts) == 2 or (len(parts) == 4 and int(parts[1]) < self.iterations)
