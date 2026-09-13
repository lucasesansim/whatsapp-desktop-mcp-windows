"""Public Pydantic models for WhatsApp Desktop MCP Windows."""

from whatsapp_desktop_mcp.models.chat import Chat, ChatKind
from whatsapp_desktop_mcp.models.contact import Contact, Jid, JidKind
from whatsapp_desktop_mcp.models.coverage import Coverage
from whatsapp_desktop_mcp.models.cursor import CursorError, decode_cursor, encode_cursor
from whatsapp_desktop_mcp.models.doctor import ComponentStatus, DoctorReport
from whatsapp_desktop_mcp.models.group import GroupInfo, GroupMember
from whatsapp_desktop_mcp.models.media import MediaRef
from whatsapp_desktop_mcp.models.message import Message, MessageKind
from whatsapp_desktop_mcp.models.send import (
    ConfirmationSchema,
    OffendingSource,
    SendResult,
    offending_source_to_pydantic,
)

__all__ = [
    "Chat",
    "ChatKind",
    "ComponentStatus",
    "ConfirmationSchema",
    "Contact",
    "Coverage",
    "CursorError",
    "DoctorReport",
    "GroupInfo",
    "GroupMember",
    "Jid",
    "JidKind",
    "MediaRef",
    "Message",
    "MessageKind",
    "OffendingSource",
    "SendResult",
    "decode_cursor",
    "encode_cursor",
    "offending_source_to_pydantic",
]
