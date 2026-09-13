"""Unit tests for cross-chat quote heuristic."""

from __future__ import annotations

from whatsapp_desktop_mcp.sender import cross_chat_quote


def test_cross_chat_quote_short_bodies_ignored() -> None:
    chat_a = 1001
    chat_b = 1002

    # Bodies shorter than 40 characters are ignored
    cross_chat_quote.record_bodies(chat_a, ["Short text 123"])
    warnings = cross_chat_quote.check(chat_b, "Short text 123")
    assert len(warnings) == 0


def test_cross_chat_quote_overlap_detected() -> None:
    chat_a = 2001
    chat_b = 2002

    long_body = (
        "This is a confidential business negotiation message with contract values 1234567890."
    )
    cross_chat_quote.record_bodies(chat_a, [long_body])

    # Checking in same chat should have NO warning
    same_chat_warnings = cross_chat_quote.check(chat_a, long_body)
    assert len(same_chat_warnings) == 0

    # Checking in different chat SHOULD detect overlap
    diff_chat_warnings = cross_chat_quote.check(chat_b, long_body)
    assert len(diff_chat_warnings) >= 1
    assert diff_chat_warnings[0].source_chat_id == chat_a
