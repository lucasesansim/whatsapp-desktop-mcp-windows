"""Time utilities for WhatsApp timestamps."""

from __future__ import annotations

import time


def now_unix() -> int:
    """Return current Unix timestamp in seconds."""
    return int(time.time())


def now_unix_ms() -> int:
    """Return current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def normalize_ts_to_seconds(ts: int | float | None) -> int | None:
    """Normalize a timestamp to Unix seconds (handling millisecond inputs)."""
    if ts is None:
        return None
    val = float(ts)
    if val > 1e11:  # Milliseconds (e.g. 1700000000000)
        return int(val / 1000)
    return int(val)
