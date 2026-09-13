"""Session-scoped cross-chat-quote heuristic (SEND-07)."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

_MAX_ENTRIES = 1000
_WINDOW_SECONDS = 30 * 60  # 30 minutes
_MIN_SUBSTRING = 40


@dataclass(frozen=True)
class _Entry:
    chat_id: int
    body: str
    recorded_at: float


@dataclass(frozen=True)
class OffendingSource:
    source_chat_id: int
    snippet: str


_lru: deque[_Entry] = deque(maxlen=_MAX_ENTRIES)


def record_bodies(chat_id: int, bodies: list[str]) -> None:
    now = time.time()
    for body in bodies:
        if body and len(body) >= _MIN_SUBSTRING:
            _lru.append(_Entry(chat_id=chat_id, body=body, recorded_at=now))


def check(target_chat_id: int, outgoing_body: str) -> list[OffendingSource]:
    if len(outgoing_body) < _MIN_SUBSTRING:
        return []
    now = time.time()
    found: list[OffendingSource] = []
    for entry in list(_lru):
        if entry.chat_id == target_chat_id:
            continue
        if now - entry.recorded_at > _WINDOW_SECONDS:
            continue
        match = _longest_shared_substring(outgoing_body, entry.body, _MIN_SUBSTRING)
        if match is not None:
            found.append(OffendingSource(source_chat_id=entry.chat_id, snippet=match[:100]))
    return found


def _longest_shared_substring(a: str, b: str, min_len: int) -> str | None:
    if len(a) < min_len or len(b) < min_len:
        return None
    for i in range(len(a) - min_len + 1):
        chunk = a[i : i + min_len]
        if chunk in b:
            j = i + min_len
            while j < len(a) and a[i : j + 1] in b:
                j += 1
            return a[i:j]
    return None


def _reset_for_test() -> None:
    _lru.clear()
