"""Unit tests for read-only mode enforcement."""

from __future__ import annotations

import pytest

from whatsapp_desktop_mcp import server
from whatsapp_desktop_mcp.exceptions import ReadOnlyModeError
from whatsapp_desktop_mcp.tools import send_message


@pytest.mark.asyncio
async def test_send_message_raises_in_read_only_mode(monkeypatch) -> None:
    server.set_read_only_mode(True)
    assert server.read_only_mode is True

    # Calling send_message directly must raise ReadOnlyModeError
    with pytest.raises((ReadOnlyModeError, ValueError)) as exc_info:
        await send_message.send_message(chat_id=123, body="Test", ctx=None)  # type: ignore

    assert "read-only" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_send_file_raises_in_read_only_mode(tmp_path) -> None:
    from whatsapp_desktop_mcp.tools import send_file

    server.set_read_only_mode(True)
    assert server.read_only_mode is True

    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"dummy pdf content")

    with pytest.raises((ReadOnlyModeError, ValueError)) as exc_info:
        await send_file.send_file(chat_id=123, file_path=str(test_file), caption="Test", ctx=None)

    assert "read-only" in str(exc_info.value).lower()
