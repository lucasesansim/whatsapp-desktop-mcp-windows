"""Unit tests for models and cursor codec."""

from __future__ import annotations

import pytest

from whatsapp_desktop_mcp.models import (
    Chat,
    Coverage,
    CursorError,
    Jid,
    Message,
    decode_cursor,
    encode_cursor,
)


def test_cursor_roundtrip() -> None:
    chat_id = 123456
    anchor = 1789308949.0
    kind = "unix_ts"

    encoded = encode_cursor(chat_id, anchor, kind)
    assert isinstance(encoded, str)

    dec_chat_id, dec_anchor, dec_kind = decode_cursor(encoded)
    assert dec_chat_id == chat_id
    assert dec_anchor == anchor
    assert dec_kind == kind


def test_cursor_malformed() -> None:
    with pytest.raises(CursorError):
        decode_cursor("not_valid_base64!!!")

    with pytest.raises(CursorError):
        # Invalid JSON inside base64
        import base64

        bad_b64 = base64.urlsafe_b64encode(b"invalid json").decode()
        decode_cursor(bad_b64)


def test_jid_parsing() -> None:
    jid1 = Jid.from_raw("5511999999999@c.us")
    assert jid1.raw == "5511999999999@c.us"
    assert jid1.kind == "phone"
    assert jid1.phone == "5511999999999"

    jid2 = Jid.from_raw("120363407498286437@g.us")
    assert jid2.raw == "120363407498286437@g.us"
    assert jid2.kind == "group"
    assert jid2.phone is None

    jid3 = Jid.from_raw("86878632038473@lid", phone="5531999999999")
    assert jid3.raw == "86878632038473@lid"
    assert jid3.kind == "lid"
    assert jid3.phone == "5531999999999"


def test_chat_model_serialization() -> None:
    coverage = Coverage(
        from_ts=1000,
        to_ts=2000,
        asked_window_seconds=1000,
        have_window_seconds=1000,
        is_full=True,
    )
    chat = Chat(
        chat_id=42,
        kind="group",
        jid=Jid.from_raw("120363407498286437@g.us"),
        display_name="Project Alpha",
        last_activity_ts=2000,
        unread_count=3,
        is_archived=False,
        is_hidden=False,
        coverage=coverage,
    )

    dumped = chat.model_dump(mode="json")
    assert dumped["chat_id"] == 42
    assert dumped["kind"] == "group"
    assert dumped["display_name"] == "Project Alpha"
    assert dumped["coverage"]["is_full"] is True


def test_message_model_serialization() -> None:
    msg = Message(
        message_id="msg_001",
        chat_id=42,
        sender_jid=Jid.from_raw("5511999999999@c.us"),
        timestamp=1789308949,
        body="Hello Antigravity",
        kind="text",
        is_outgoing=True,
        is_starred=False,
    )

    dumped = msg.model_dump(mode="json")
    assert dumped["message_id"] == "msg_001"
    assert dumped["body"] == "Hello Antigravity"
    assert dumped["is_outgoing"] is True
