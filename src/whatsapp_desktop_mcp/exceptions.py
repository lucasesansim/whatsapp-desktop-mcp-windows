"""Custom exceptions hierarchy for WhatsApp Desktop MCP Windows."""

from __future__ import annotations


class WhatsAppError(Exception):
    """Base exception for all WhatsApp MCP errors."""


class WhatsAppNotRunningError(WhatsAppError):
    """Raised when the WhatsApp Desktop application process is not running."""


class CDPConnectionError(WhatsAppError):
    """Raised when the Chrome DevTools Protocol endpoint cannot be reached."""


class TargetNotFoundError(WhatsAppError):
    """Raised when the WhatsApp page target is not found among CDP targets."""


class ReadOnlyModeError(WhatsAppError):
    """Raised when a send operation is attempted in read-only mode."""


class RateLimitExceeded(WhatsAppError):
    """Raised when a send attempt violates sliding-window rate limits."""

    def __init__(self, message: str, retry_after_seconds: int = 60) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class InvalidChatId(WhatsAppError):
    """Raised when a chat_id cannot be resolved or is invalid."""


class ChatHeaderMismatch(WhatsAppError):
    """Raised when the active chat title does not match the expected recipient."""


class SendTimeout(WhatsAppError):
    """Raised when a UI automation or CDP operation times out."""


class SendConfirmationDeclined(WhatsAppError):
    """Raised when the user declines the elicitation confirmation prompt."""
