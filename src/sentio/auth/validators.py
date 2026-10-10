import re

from sentio.auth.exceptions import ValidationError


class PasswordValidator:
    """Validates password strength according to standard security rules."""

    def __init__(self, min_length: int = 8):
        self.min_length = min_length

    def validate(self, password: str):
        """
        Enforces password complexity:
          - length >= min_length
          - contains at least one uppercase letter
          - contains at least one lowercase letter
          - contains at least one digit
          - contains at least one special character
        """
        if len(password) < self.min_length:
            raise ValidationError(f"Password must be at least {self.min_length} characters long.")

        if not re.search(r"[A-Z]", password):
            raise ValidationError("Password must contain at least one uppercase letter.")

        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must contain at least one lowercase letter.")

        if not re.search(r"\d", password):
            raise ValidationError("Password must contain at least one digit.")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValidationError("Password must contain at least one special character.")
