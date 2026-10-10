class AuthException(Exception):
    """Base exception for all authentication and authorization errors."""

    pass


class CredentialsError(AuthException):
    """Raised when credentials (password or email) are invalid."""

    pass


class ExpiredTokenError(AuthException):
    """Raised when a token has expired."""

    pass


class InvalidTokenError(AuthException):
    """Raised when a token signature is invalid or formatted incorrectly."""

    pass


class PermissionDeniedError(AuthException):
    """Raised when a user lacks the required role or permissions."""

    pass


class ValidationError(AuthException):
    """Raised when registration input does not meet criteria."""

    pass
