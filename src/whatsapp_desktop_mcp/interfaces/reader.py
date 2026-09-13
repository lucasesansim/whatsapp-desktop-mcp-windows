"""Abstract interface for reading WhatsApp data."""

from __future__ import annotations

from abc import ABC, abstractmethod

from whatsapp_desktop_mcp.models.chat import Chat
from whatsapp_desktop_mcp.models.contact import Contact
from whatsapp_desktop_mcp.models.group import GroupInfo
from whatsapp_desktop_mcp.models.message import Message


class WhatsAppReader(ABC):
    """Abstract interface defining all read operations for WhatsApp."""

    @abstractmethod
    async def list_chats(self, limit: int = 200) -> list[Chat]:
        """List active conversations ordered by latest activity descending."""

    @abstractmethod
    async def find_chat_by_id(self, chat_id: int) -> Chat | None:
        """Find a chat by its integer chat_id."""

    @abstractmethod
    async def find_chat_by_jid(self, jid_raw: str) -> Chat | None:
        """Find a chat by its JID string."""

    @abstractmethod
    async def read_chat(
        self,
        chat_id: int,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None]:
        """Read a window of messages from a chat with cursor pagination."""

    @abstractmethod
    async def extract_recent(
        self, since_ts: int, chat_id: int | None = None, limit: int = 200
    ) -> list[Message]:
        """Extract messages since a given Unix timestamp, optionally filtered by chat_id."""

    @abstractmethod
    async def search_messages(
        self,
        query: str,
        chat_id: int | None = None,
        limit: int = 100,
    ) -> list[Message]:
        """Search message bodies matching query string."""

    @abstractmethod
    async def search_contacts(self, query: str, limit: int = 50) -> list[Contact]:
        """Search contacts by display name or phone number."""

    @abstractmethod
    async def get_chat_metadata(self, chat_id: int) -> GroupInfo | None:
        """Get deep metadata and participant roster for a group chat."""

    @abstractmethod
    async def get_message_context(
        self,
        message_id: str,
        before: int = 5,
        after: int = 5,
    ) -> tuple[list[Message], Message | None]:
        """Get context messages before and after a specific message ID."""
