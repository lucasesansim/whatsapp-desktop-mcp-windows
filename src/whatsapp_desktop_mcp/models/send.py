"""Public Pydantic surface for send_message."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from whatsapp_desktop_mcp.sender.cross_chat_quote import (
        OffendingSource as _CCQOffendingSource,
    )


class SendResult(BaseModel):
    """The send_message return shape."""

    status: Literal[
        "sent",
        "sent_unverified",
        "cancelled",
        "rate_limited",
        "error",
    ]
    message_id: str | None = None
    chat_id: int
    chat_name: str
    verification_note: str | None = None
    rate_limit_remaining_per_min: int | None = None
    rate_limit_remaining_per_day: int | None = None
    audit_log_path: str | None = None
    elapsed_ms: int = 0
    is_experimental: bool = False
    confirm_skipped: bool = False


class SendFileResult(BaseModel):
    """The send_file return shape."""

    status: Literal[
        "sent",
        "sent_unverified",
        "cancelled",
        "rate_limited",
        "error",
    ]
    message_id: str | None = None
    chat_id: int
    chat_name: str
    file_name: str
    file_size_bytes: int
    caption: str | None = None
    verification_note: str | None = None
    rate_limit_remaining_per_min: int | None = None
    rate_limit_remaining_per_day: int | None = None
    audit_log_path: str | None = None
    elapsed_ms: int = 0
    is_experimental: bool = False
    confirm_skipped: bool = False


class OffendingSource(BaseModel):
    """Pydantic representation of a cross-chat quote warning."""

    source_chat_id: int
    snippet: str


def offending_source_to_pydantic(src: _CCQOffendingSource) -> OffendingSource:
    return OffendingSource(source_chat_id=src.source_chat_id, snippet=src.snippet)


class ConfirmationSchema(BaseModel):
    """Schema passed to ctx.elicit(message, schema=ConfirmationSchema)."""

    confirm: bool = Field(description="Send this WhatsApp message?")
