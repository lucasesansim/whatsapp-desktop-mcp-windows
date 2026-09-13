"""Abstract interface for sending messages through WhatsApp Desktop."""

from __future__ import annotations

from abc import ABC, abstractmethod

from whatsapp_desktop_mcp.models.chat import Chat


class WhatsAppTransport(ABC):
    """Abstract interface defining the send operation."""

    @abstractmethod
    async def assert_recipient(self, chat: Chat) -> None:
        """Verify that the currently focused or active conversation matches the intended chat."""

    @abstractmethod
    async def send_text(self, chat: Chat, body: str) -> tuple[bool, int]:
        """Send a message to the target chat.

        Returns (is_experimental, send_started_unix_ts).
        """

    @abstractmethod
    async def send_file(
        self,
        chat: Chat,
        file_path: str,
        caption: str = "",
    ) -> tuple[bool, int]:
        """Send a file (PDF, image, document) to the target chat.

        Returns (is_experimental, send_started_unix_ts).
        """

    @abstractmethod
    async def verify_outgoing(
        self,
        chat: Chat,
        body: str,
        start_ts: int,
        timeout_seconds: float = 10.0,
    ) -> str | None:
        """Poll to verify that the outgoing message was recorded.

        Returns the message_id or None if verification timed out.
        """
