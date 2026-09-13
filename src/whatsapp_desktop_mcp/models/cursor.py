"""Opaque pagination cursor — base64-encoded JSON."""

from __future__ import annotations

import base64
import json
from typing import Literal

AnchorKind = Literal["z_sort", "cocoa_ts", "unix_ts", "offset"]
_VALID_ANCHOR_KINDS: frozenset[str] = frozenset({"z_sort", "cocoa_ts", "unix_ts", "offset"})


class CursorError(ValueError):
    """Raised by ``decode_cursor`` on any malformed cursor payload."""


def encode_cursor(chat_id: int, anchor: float, anchor_kind: AnchorKind = "unix_ts") -> str:
    """Encode a pagination cursor as a URL-safe base64 JSON string."""
    payload = json.dumps(
        {"chat_id": chat_id, "anchor": anchor, "anchor_kind": anchor_kind},
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decode_cursor(cursor: str) -> tuple[int, float, AnchorKind]:
    """Decode a cursor produced by :func:`encode_cursor`."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise CursorError("invalid cursor") from exc

    if not isinstance(payload, dict):
        raise CursorError("invalid cursor")

    expected_keys = {"chat_id", "anchor", "anchor_kind"}
    if set(payload.keys()) != expected_keys:
        raise CursorError("invalid cursor")

    chat_id = payload["chat_id"]
    anchor = payload["anchor"]
    anchor_kind = payload["anchor_kind"]

    if not isinstance(chat_id, int) or isinstance(chat_id, bool):
        raise CursorError("invalid cursor")
    if not isinstance(anchor, (int, float)) or isinstance(anchor, bool):
        raise CursorError("invalid cursor")
    if anchor_kind not in _VALID_ANCHOR_KINDS:
        raise CursorError("invalid cursor")

    return chat_id, float(anchor), anchor_kind
