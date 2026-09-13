"""Group — metadata and member roster."""

from __future__ import annotations

from pydantic import BaseModel, Field

from whatsapp_desktop_mcp.models.contact import Jid


class GroupMember(BaseModel):
    """One group participant."""

    jid: Jid
    display_name: str = ""
    is_admin: bool = False
    is_active: bool = True


class GroupInfo(BaseModel):
    """Group metadata: subject, participants, admin flags."""

    chat_id: int
    subject: str
    description: str | None = None
    creation_ts: int | None = None
    creator_jid: Jid | None = None
    owner_jid: Jid | None = None
    members: list[GroupMember] = Field(default_factory=list)
    is_muted: bool = False
