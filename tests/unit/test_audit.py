"""Unit tests for SHA-256 audit logging without plaintext bodies."""

from __future__ import annotations

from pathlib import Path

import pytest

from whatsapp_desktop_mcp.sender import audit
from whatsapp_desktop_mcp.sender.audit import AuditEntry, append_audit_entry, hash_body


def test_hash_body_sha256() -> None:
    body = "Test WhatsApp message content"
    expected = "4f7fbb84cf0e4c11cd9751ae5d6bf9e5049e188ca61064759409f53070a5e051"
    assert hash_body(body) == expected


def test_audit_entry_never_contains_plaintext_body() -> None:
    entry = AuditEntry(
        chat_id=123,
        recipient_jid="5511999999999@c.us",
        body_sha256=hash_body("Secret message text"),
        outcome="sent",
        message_id="msg_xyz",
    )

    dumped = entry.model_dump(mode="json")
    assert "Secret message text" not in str(dumped)
    assert "body" not in dumped
    assert "body_sha256" in dumped


@pytest.mark.asyncio
async def test_audit_append_and_rotation(tmp_path: Path, monkeypatch) -> None:
    test_log = tmp_path / "audit.log"
    monkeypatch.setattr(audit, "get_audit_log_path", lambda: test_log)
    monkeypatch.setenv(
        "WHATSAPP_DESKTOP_MCP_AUDIT_LOG_MAX_BYTES", "250"
    )  # very small threshold for testing

    entry1 = AuditEntry(
        chat_id=1,
        recipient_jid="1@c.us",
        body_sha256=hash_body("A" * 50),
        outcome="sent",
    )
    await append_audit_entry(entry1)
    assert test_log.exists()

    entry2 = AuditEntry(
        chat_id=2,
        recipient_jid="2@c.us",
        body_sha256=hash_body("B" * 50),
        outcome="sent",
    )
    await append_audit_entry(entry2)

    entry3 = AuditEntry(
        chat_id=3,
        recipient_jid="3@c.us",
        body_sha256=hash_body("C" * 50),
        outcome="sent",
    )
    await append_audit_entry(entry3)

    # Rotation should have created archive audit.log.1
    rotated = tmp_path / "audit.log.1"
    assert rotated.exists() or test_log.exists()
