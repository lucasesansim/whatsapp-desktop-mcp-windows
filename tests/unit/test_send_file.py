"""Unit tests for send_file tool."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.elicitation import AcceptedElicitation

from whatsapp_desktop_mcp import server
from whatsapp_desktop_mcp.models.chat import Chat
from whatsapp_desktop_mcp.models.contact import Jid
from whatsapp_desktop_mcp.models.send import ConfirmationSchema
from whatsapp_desktop_mcp.tools import send_file


@pytest.mark.asyncio
async def test_send_file_nonexistent_raises(monkeypatch) -> None:
    server.set_read_only_mode(False)
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_SKIP_CONFIRM", "1")

    with pytest.raises(FileNotFoundError):
        await send_file.send_file(
            chat_id=12345,
            file_path="C:\\nonexistent\\path\\to\\report.pdf",
            caption="Test",
        )


@pytest.mark.asyncio
async def test_send_file_oversized_raises(tmp_path, monkeypatch) -> None:
    server.set_read_only_mode(False)
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_SKIP_CONFIRM", "1")

    fake_file = tmp_path / "huge.bin"
    fake_file.write_bytes(b"small")

    # Mock getsize to simulate > 100MB
    with patch("os.path.getsize", return_value=150 * 1024 * 1024):
        with pytest.raises(ValueError, match="exceeds 100MB"):
            await send_file.send_file(
                chat_id=12345,
                file_path=str(fake_file),
                caption="Huge",
            )


@pytest.mark.asyncio
async def test_send_file_successful_flow(tmp_path, monkeypatch) -> None:
    server.set_read_only_mode(False)
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_SKIP_CONFIRM", "1")

    # Create dummy pdf
    pdf_file = tmp_path / "relatorio_projeto.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy architectural report bytes")

    # Mock reader.find_chat_by_id
    from whatsapp_desktop_mcp.models.coverage import Coverage

    mock_chat = Chat(
        chat_id=99999,
        jid=Jid.from_raw("5511999999999@c.us"),
        display_name="Cliente Exemplo",
        kind="direct",
        coverage=Coverage(
            chat_id=99999,
            has_messages=True,
            newest_message_unix_ts=1700000000,
        ),
    )
    monkeypatch.setattr(server.reader, "find_chat_by_id", AsyncMock(return_value=mock_chat))

    # Mock transport.send_file and verify_outgoing
    monkeypatch.setattr(
        server.transport,
        "send_file",
        AsyncMock(return_value=(False, 1700000000)),
    )
    monkeypatch.setattr(
        server.transport,
        "verify_outgoing",
        AsyncMock(return_value="true_5511999999999@c.us_3EB012345678"),
    )

    result = await send_file.send_file(
        chat_id=99999,
        file_path=str(pdf_file),
        caption="Segue o relatório em anexo", ctx=SimpleNamespace(elicit=AsyncMock(return_value=AcceptedElicitation(data=ConfirmationSchema(confirm=True)))),
    )

    assert result.status == "sent"
    assert result.message_id == "true_5511999999999@c.us_3EB012345678"
    assert result.chat_id == 99999
    assert result.chat_name == "Cliente Exemplo"
    assert result.file_name == "relatorio_projeto.pdf"
    assert result.file_size_bytes > 0
    assert result.caption == "Segue o relatório em anexo"
    assert result.audit_log_path is not None
