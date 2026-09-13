"""Chat — model for conversation metadata."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from whatsapp_desktop_mcp.models.contact import Jid
from whatsapp_desktop_mcp.models.coverage import Coverage

ChatKind = Literal["direct", "group", "broadcast", "community", "other"]


class Chat(BaseModel):
    """Normalized chat conversation for tool output."""

    chat_id: int
    kind: ChatKind
    jid: Jid
    display_name: str
    last_activity_ts: int | None = None
    last_message_preview: str | None = None
    unread_count: int = 0
    is_archived: bool = False
    is_hidden: bool = False
    coverage: Coverage
