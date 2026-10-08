"""Exact comparisons for observed outgoing messages; never infer delivery."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

_JID = re.compile(r"^[0-9]+(?:-[0-9]+)?@(?:c\.us|s\.whatsapp\.net|g\.us|lid)$")


def validate_jid(value: str) -> str:
    if not isinstance(value, str) or not _JID.fullmatch(value):
        raise ValueError("Unsupported or malformed WhatsApp recipient identifier.")
    return value


def normalize_text(value: str) -> str:
    # Preserve spaces, emoji, punctuation and case. Only normalize platform line endings.
    return value.replace("\r\n", "\n").replace("\r", "\n")


@dataclass
class PendingSend:
    recipient: str
    body: str
    started: int
    previous_ids: set[str] = field(default_factory=set)
    filename: str | None = None
    size: int | None = None

    def match(self, record: dict[str, Any]) -> str | None:
        message_id = record.get("id")
        if not isinstance(message_id, str) or not message_id or message_id in self.previous_ids:
            return None
        if record.get("to") != self.recipient or record.get("fromMe") is not True:
            return None
        timestamp = record.get("t")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            return None
        if not math.isfinite(timestamp) or timestamp < self.started:
            return None
        if self.filename is None:
            if record.get("type") not in ("chat", "text"):
                return None
            body = record.get("body")
            if not isinstance(body, str) or normalize_text(body) != normalize_text(self.body):
                return None
        else:
            if record.get("type") not in ("document", "image", "video", "audio", "ptt"):
                return None
            if record.get("filename") != self.filename or record.get("size") != self.size:
                return None
            caption = record.get("caption")
            if not isinstance(caption, str) or normalize_text(caption) != normalize_text(self.body):
                return None
        return message_id
