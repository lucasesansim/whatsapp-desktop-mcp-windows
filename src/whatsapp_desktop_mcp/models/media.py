"""MediaRef — attachment metadata only; never inline bytes."""

from __future__ import annotations

from pydantic import BaseModel


class MediaRef(BaseModel):
    """Reference to an attachment file on disk."""

    local_path: str = ""
    filename: str = ""
    mime: str = ""
    size_bytes: int = 0
    duration_seconds: float | None = None
    latitude: float | None = None
    longitude: float | None = None
