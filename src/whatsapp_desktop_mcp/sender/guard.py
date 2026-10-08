"""Exclude overlapping sends across MCP processes sharing the same local profile."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from whatsapp_desktop_mcp.paths import get_mcp_data_dir

_in_progress = False


@asynccontextmanager
async def exclusive_send():
    global _in_progress
    if _in_progress:
        raise RuntimeError("Another send is in progress. No message was sent by this request.")
    _in_progress = True
    handle = None
    locked = False
    try:
        handle = (get_mcp_data_dir() / "send.lock").open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError:
            raise RuntimeError("Another MCP process is sending. This request was blocked.") from None
        yield
    finally:
        try:
            if handle is not None:
                try:
                    if locked:
                        handle.seek(0)
                        if os.name == "nt":
                            import msvcrt

                            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl

                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()
        finally:
            _in_progress = False
