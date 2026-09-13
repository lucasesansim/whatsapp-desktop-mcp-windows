"""Sender safety components (rate limiter, audit logger, cross-chat quote guard)."""

from whatsapp_desktop_mcp.sender.audit import AuditEntry, append_audit_entry, hash_body
from whatsapp_desktop_mcp.sender.cross_chat_quote import check as check_cross_chat_quote
from whatsapp_desktop_mcp.sender.cross_chat_quote import record_bodies as record_cross_chat_bodies
from whatsapp_desktop_mcp.sender.rate_limit import (
    check_and_reserve,
    record_outcome,
    reset_rate_limit_sync,
)

__all__ = [
    "AuditEntry",
    "append_audit_entry",
    "check_and_reserve",
    "check_cross_chat_quote",
    "hash_body",
    "record_cross_chat_bodies",
    "record_outcome",
    "reset_rate_limit_sync",
]
