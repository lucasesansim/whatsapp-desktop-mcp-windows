"""Message — model for individual messages."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from whatsapp_desktop_mcp.models.contact import Jid
from whatsapp_desktop_mcp.models.media import MediaRef

MessageKind = Literal[
    "text",
    "image",
    "video",
    "audio",
    "system",
    "location",
    "contact",
    "sticker",
    "call",
    "revoked",
    "ephemeral",
    "poll",
    "reaction",
    "other",
]


class Message(BaseModel):
    """Normalized message for tool output."""

    message_id: str
    chat_id: int
    sender_jid: Jid
    timestamp: int
    body: str | None = None
    kind: MessageKind = "text"
    is_outgoing: bool = False
    is_starred: bool = False
    quoted_message_id: str | None = None
    media: MediaRef | None = None
