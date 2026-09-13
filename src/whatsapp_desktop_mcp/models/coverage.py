"""Coverage — disclosure of cache window vs full history."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Coverage(BaseModel):
    """Cache-vs-truth disclosure for every read response."""

    from_ts: int | None = Field(
        default=None,
        description="Unix timestamp (seconds) of the earliest message in the actual data window.",
    )
    to_ts: int | None = Field(
        default=None,
        description="Unix timestamp (seconds) of the latest message in the actual data window.",
    )
    asked_window_seconds: int | None = Field(
        default=None,
        description="The window the caller requested (extract_recent only; null for read_chat by limit).",
    )
    have_window_seconds: int | None = Field(
        default=None,
        description="The window actually present in the local cache (to_ts - from_ts).",
    )
    is_full: bool = Field(
        default=True,
        description="True if the local cache covered the entire asked window.",
    )
