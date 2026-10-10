"""
exceptions.py — Custom Exceptions for Sentio
=============================================
Defines standard exceptions for runtime error propagation and handling.
"""


class LLMServiceUnavailableError(Exception):
    """Raised when the LLM service is offline, unreachable, or has model loading issues."""

    def __init__(self, backend_name: str, message: str):
        self.backend_name = backend_name
        self.message = message
        super().__init__(f"LLM backend '{backend_name}' is currently unavailable: {message}")
