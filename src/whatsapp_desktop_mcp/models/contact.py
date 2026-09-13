"""Contact / Jid types — kind-tagged, never compared as strings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JidKind = Literal["phone", "lid", "group", "broadcast", "status"]


class Jid(BaseModel):
    """A WhatsApp identifier, kind-tagged so comparisons are always typed."""

    kind: JidKind
    raw: str
    phone: str | None = None
    lid: str | None = None

    @classmethod
    def from_raw(cls, raw: str, phone: str | None = None, lid: str | None = None) -> Jid:
        raw_str = str(raw or "")
        if raw_str.endswith("@g.us"):
            return cls(kind="group", raw=raw_str)
        elif raw_str.endswith("@broadcast"):
            return cls(kind="broadcast", raw=raw_str)
        elif raw_str == "0@status" or "status" in raw_str:
            return cls(kind="status", raw=raw_str)
        elif raw_str.endswith("@lid"):
            lid_val = lid or raw_str.split("@")[0]
            return cls(kind="lid", raw=raw_str, phone=phone, lid=lid_val)
        else:
            # @s.whatsapp.net or @c.us or digits
            digits = "".join(filter(str.isdigit, raw_str.split("@")[0]))
            return cls(kind="phone", raw=raw_str, phone=digits or phone, lid=lid)


class Contact(BaseModel):
    """A WhatsApp contact / chat partner with all known identifiers merged."""

    display_name: str
    jid: Jid
    known_identifiers: list[Jid] = Field(default_factory=list)
    chat_id: int | None = None
    last_message_preview: str | None = None
    last_message_ts: int | None = None
    disambiguation_required: bool = False
