"""Persistent SQLite-backed rate limiter for WhatsApp send attempts."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import time

from whatsapp_desktop_mcp.exceptions import RateLimitExceeded
from whatsapp_desktop_mcp.paths import get_rate_limit_db_path

DEFAULT_RATE_PER_MIN = 5
DEFAULT_RATE_PER_DAY = 30
HARD_MAX_RATE_PER_MIN = 20
HARD_MAX_RATE_PER_DAY = 200

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    body_sha256 TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('sent', 'sent_unverified', 'cancelled', 'rate_limited', 'error'))
);
CREATE INDEX IF NOT EXISTS idx_sends_ts ON sends(ts);
"""


def _resolve_limits() -> tuple[int, int]:
    raw_min = os.environ.get("WHATSAPP_DESKTOP_MCP_RATE_PER_MIN")
    raw_day = os.environ.get("WHATSAPP_DESKTOP_MCP_RATE_PER_DAY")

    per_min = int(raw_min) if raw_min else DEFAULT_RATE_PER_MIN
    per_day = int(raw_day) if raw_day else DEFAULT_RATE_PER_DAY

    if per_min > HARD_MAX_RATE_PER_MIN:
        raise ValueError(
            f"WHATSAPP_DESKTOP_MCP_RATE_PER_MIN={per_min} exceeds hard maximum {HARD_MAX_RATE_PER_MIN}"
        )
    if per_day > HARD_MAX_RATE_PER_DAY:
        raise ValueError(
            f"WHATSAPP_DESKTOP_MCP_RATE_PER_DAY={per_day} exceeds hard maximum {HARD_MAX_RATE_PER_DAY}"
        )

    return per_min, per_day


def _get_connection() -> sqlite3.Connection:
    db_path = get_rate_limit_db_path()
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(_SCHEMA)
    return conn


def _check_and_reserve_sync() -> tuple[int, int]:
    per_min, per_day = _resolve_limits()
    now = int(time.time())
    one_min_ago = now - 60
    one_day_ago = now - 86400

    with _get_connection() as conn:
        count_min = conn.execute(
            "SELECT COUNT(*) FROM sends WHERE ts >= ? AND outcome IN ('sent', 'sent_unverified')",
            (one_min_ago,),
        ).fetchone()[0]

        count_day = conn.execute(
            "SELECT COUNT(*) FROM sends WHERE ts >= ? AND outcome IN ('sent', 'sent_unverified')",
            (one_day_ago,),
        ).fetchone()[0]

        if count_min >= per_min:
            raise RateLimitExceeded(
                f"Rate limit exceeded: {count_min}/{per_min} sends in the last 60 seconds.",
                retry_after_seconds=60,
            )
        if count_day >= per_day:
            raise RateLimitExceeded(
                f"Daily rate limit exceeded: {count_day}/{per_day} sends in the last 24 hours.",
                retry_after_seconds=3600,
            )

        return per_min - count_min, per_day - count_day


async def check_and_reserve() -> tuple[int, int]:
    """Check sliding window rate limits without incrementing counters."""
    return await asyncio.to_thread(_check_and_reserve_sync)


def _record_outcome_sync(chat_id: int, body_sha256: str, outcome: str) -> None:
    now = int(time.time())
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO sends (ts, chat_id, body_sha256, outcome) VALUES (?, ?, ?, ?)",
            (now, chat_id, body_sha256, outcome),
        )
        conn.commit()


async def record_outcome(chat_id: int, body_sha256: str, outcome: str) -> None:
    """Record send outcome in rate limiter database."""
    await asyncio.to_thread(_record_outcome_sync, chat_id, body_sha256, outcome)


def reset_rate_limit_sync() -> None:
    """Clear all records from the rate limit table."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM sends")
        conn.commit()
