"""JSONL audit log for WhatsApp send attempts."""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from whatsapp_desktop_mcp.paths import get_audit_log_path

_DEFAULT_MAX_BYTES = 10 * 1024 * 1024
_ENV_MAX_BYTES = "WHATSAPP_DESKTOP_MCP_AUDIT_LOG_MAX_BYTES"
_ARCHIVE_COUNT = 5

Outcome = Literal[
    "sent",
    "sent_unverified",
    "cancelled",
    "rate_limited",
    "error",
]


class AuditEntry(BaseModel):
    """One audit-log row."""

    ts: int = Field(default_factory=lambda: int(time.time()))
    chat_id: int
    recipient_jid: str
    body_sha256: str
    file_sha256: str | None = None
    file_name: str | None = None
    outcome: Outcome
    message_id: str | None = None
    rate_limit_remaining_per_min: int | None = None
    rate_limit_remaining_per_day: int | None = None
    elapsed_ms: int = 0
    confirm_skipped: bool = False
    error_message: str | None = None


def hash_body(body: str) -> str:
    """Return SHA-256 lowercase hex digest of message body."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def hash_file(file_path: str | Path) -> str:
    """Return SHA-256 lowercase hex digest of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _resolve_max_bytes() -> int:
    env_val = os.environ.get(_ENV_MAX_BYTES)
    if env_val:
        try:
            return int(env_val)
        except ValueError:
            pass
    return _DEFAULT_MAX_BYTES


def _rotate_if_needed(log_path: Path, max_bytes: int) -> None:
    if not log_path.exists():
        return
    try:
        if log_path.stat().st_size < max_bytes:
            return

        oldest = log_path.with_name(f"{log_path.name}.{_ARCHIVE_COUNT}")
        if oldest.exists():
            oldest.unlink()

        for i in range(_ARCHIVE_COUNT - 1, 0, -1):
            src = log_path.with_name(f"{log_path.name}.{i}")
            dst = log_path.with_name(f"{log_path.name}.{i + 1}")
            if src.exists():
                src.rename(dst)

        first_archive = log_path.with_name(f"{log_path.name}.1")
        log_path.rename(first_archive)
    except Exception:
        pass


def _blocking_append(entry: AuditEntry) -> None:
    log_path = get_audit_log_path()
    max_bytes = _resolve_max_bytes()
    _rotate_if_needed(log_path, max_bytes)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")


async def append_audit_entry(entry: AuditEntry) -> None:
    """Asynchronously append an entry to the audit log."""
    await asyncio.to_thread(_blocking_append, entry)
