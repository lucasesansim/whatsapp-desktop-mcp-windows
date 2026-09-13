"""``send_message`` MCP tool for WhatsApp Desktop on Windows."""

from __future__ import annotations

import logging
import os
import time
from typing import Literal

from mcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from whatsapp_desktop_mcp import server
from whatsapp_desktop_mcp.exceptions import (
    ChatHeaderMismatch,
    InvalidChatId,
    RateLimitExceeded,
    ReadOnlyModeError,
    SendTimeout,
)
from whatsapp_desktop_mcp.models.contact import Jid
from whatsapp_desktop_mcp.models.send import ConfirmationSchema, SendResult
from whatsapp_desktop_mcp.paths import get_audit_log_path
from whatsapp_desktop_mcp.sender import cross_chat_quote, rate_limit
from whatsapp_desktop_mcp.sender.audit import AuditEntry, append_audit_entry, hash_body
from whatsapp_desktop_mcp.sender.cross_chat_quote import OffendingSource
from whatsapp_desktop_mcp.server import mcp
from whatsapp_desktop_mcp.tools._decorators import timeout

logger = logging.getLogger(__name__)


def _build_elicitation_message(
    *,
    chat_name: str,
    chat_id: int,
    recipient_jid: Jid,
    chars_in_body: int,
    body_verbatim: str,
    warnings: list[OffendingSource],
    rate_min_rem: int,
    rate_day_rem: int,
) -> str:
    if warnings:
        warnings_str = "\n".join(
            f"  - {chars_in_body}-char overlap with chat_id={w.source_chat_id}: {w.snippet!r}"
            for w in warnings
        )
    else:
        warnings_str = "none"
    return (
        f"Send this message via WhatsApp Desktop?\n\n"
        f"Chat: {chat_name}  (id={chat_id}, jid={recipient_jid.raw} kind={recipient_jid.kind})\n"
        f"Body ({chars_in_body} chars):\n"
        f"---\n{body_verbatim}\n---\n"
        f"Cross-chat warnings: {warnings_str}\n"
        f"Rate budget: {rate_min_rem}/min, {rate_day_rem}/day remaining."
    )


@mcp.tool(
    name="send_message",
    title="Send a WhatsApp text message",
    description=(
        "Sends a text message to one resolved chat (by opaque chat_id from "
        "search_contacts / list_chats — never a free-form name string). "
        "Gated by an MCP elicitation prompt showing resolved chat name, "
        "recipient JID, and body verbatim — decline cancels cleanly. Group "
        "sends are experimental. Conservative rate limits apply by default "
        "(5/min, 30/day). The pre-send state assertion aborts on focused-chat "
        "mismatch. WhatsApp's Terms of Service prohibit automated / bulk "
        "messaging; use sparingly, never for marketing or broadcast."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
    meta={"anthropic/maxResultSizeChars": 60_000},
)
@timeout(seconds=15)
async def send_message(
    chat_id: int,
    body: str,
    ctx: Context,  # type: ignore[type-arg]
) -> SendResult:
    """Send one text message via WhatsApp Desktop on Windows."""
    send_started_unix = time.time()
    sha = hash_body(body)
    outcome: Literal["sent", "sent_unverified", "cancelled", "rate_limited", "error"] = "error"
    message_id: str | None = None
    err_msg: str | None = None
    verification_note: str | None = None
    rate_min_rem: int | None = None
    rate_day_rem: int | None = None
    chat_name = "<unresolved>"
    recipient_jid_str = ""
    is_experimental = False
    confirm_skipped = False
    audit_log_path = str(get_audit_log_path())

    try:
        # STEP 1: read_only_mode check
        if server.read_only_mode:
            raise ReadOnlyModeError(
                "Server started with --read-only. To enable sends, restart with --no-read-only."
            )

        # STEP 2: chat_id validation
        chat = await server.reader.find_chat_by_id(chat_id)
        if chat is None:
            raise InvalidChatId(
                f"chat_id={chat_id} does not resolve to any chat in the local DB. "
                f"Use search_contacts or list_chats to discover valid chat_ids."
            )
        chat_name = chat.display_name
        recipient_jid_str = chat.jid.raw

        # STEP 3: cross-chat-quote check
        warnings = cross_chat_quote.check(chat_id, body)

        # STEP 4: rate-limit check
        rate_min_rem, rate_day_rem = await rate_limit.check_and_reserve()

        # STEP 5: MCP elicitation
        if os.environ.get("WHATSAPP_DESKTOP_MCP_SKIP_CONFIRM") == "1":
            confirm_skipped = True
        else:
            prompt = _build_elicitation_message(
                chat_name=chat_name,
                chat_id=chat_id,
                recipient_jid=chat.jid,
                chars_in_body=len(body),
                body_verbatim=body,
                warnings=warnings,
                rate_min_rem=rate_min_rem,
                rate_day_rem=rate_day_rem,
            )
            result = await ctx.elicit(message=prompt, schema=ConfirmationSchema)
            if isinstance(result, (DeclinedElicitation, CancelledElicitation)):
                outcome = "cancelled"
                return SendResult(
                    status="cancelled",
                    message_id=None,
                    chat_id=chat_id,
                    chat_name=chat_name,
                    verification_note=None,
                    rate_limit_remaining_per_min=rate_min_rem,
                    rate_limit_remaining_per_day=rate_day_rem,
                    audit_log_path=audit_log_path,
                    elapsed_ms=int((time.time() - send_started_unix) * 1000),
                    is_experimental=False,
                    confirm_skipped=False,
                )
            assert isinstance(result, AcceptedElicitation)
            if not result.data.confirm:
                outcome = "cancelled"
                return SendResult(
                    status="cancelled",
                    message_id=None,
                    chat_id=chat_id,
                    chat_name=chat_name,
                    verification_note=None,
                    rate_limit_remaining_per_min=rate_min_rem,
                    rate_limit_remaining_per_day=rate_day_rem,
                    audit_log_path=audit_log_path,
                    elapsed_ms=int((time.time() - send_started_unix) * 1000),
                    is_experimental=False,
                    confirm_skipped=False,
                )

        # STEP 6: Drive send via CDP transport
        is_experimental, start_ts = await server.transport.send_text(chat, body)

        # STEP 7: Post-hoc DB poll
        message_id = await server.transport.verify_outgoing(chat, body, start_ts)
        if message_id is not None:
            outcome = "sent"
        else:
            outcome = "sent_unverified"
            verification_note = (
                "Send observably succeeded in the WhatsApp UI but the corresponding "
                "message was not visible in IndexedDB within the verification window. "
                "DO NOT retry immediately to prevent duplicates."
            )

        status_literal: Literal["sent", "sent_unverified"] = (
            "sent" if message_id is not None else "sent_unverified"
        )
        return SendResult(
            status=status_literal,
            message_id=message_id,
            chat_id=chat_id,
            chat_name=chat_name,
            verification_note=verification_note,
            rate_limit_remaining_per_min=rate_min_rem,
            rate_limit_remaining_per_day=rate_day_rem,
            audit_log_path=audit_log_path,
            elapsed_ms=int((time.time() - send_started_unix) * 1000),
            is_experimental=is_experimental,
            confirm_skipped=confirm_skipped,
        )

    except ReadOnlyModeError as exc:
        outcome = "error"
        err_msg = "ReadOnlyModeError"
        raise ValueError(str(exc)) from exc
    except InvalidChatId as exc:
        outcome = "error"
        err_msg = "InvalidChatId"
        raise ValueError(str(exc)) from exc
    except RateLimitExceeded as exc:
        outcome = "rate_limited"
        err_msg = "RateLimitExceeded"
        raise ValueError(str(exc)) from exc
    except (ChatHeaderMismatch, SendTimeout) as exc:
        outcome = "error"
        err_msg = type(exc).__name__
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        outcome = "error"
        err_msg = type(exc).__name__
        raise ValueError(f"Send failed: {exc}") from exc
    finally:
        try:
            await append_audit_entry(
                AuditEntry(
                    chat_id=chat_id,
                    recipient_jid=recipient_jid_str,
                    body_sha256=sha,
                    outcome=outcome,
                    message_id=message_id,
                    rate_limit_remaining_per_min=rate_min_rem,
                    rate_limit_remaining_per_day=rate_day_rem,
                    elapsed_ms=int((time.time() - send_started_unix) * 1000),
                    confirm_skipped=confirm_skipped,
                    error_message=err_msg,
                )
            )
            await rate_limit.record_outcome(chat_id, sha, outcome)
        except Exception:
            logger.exception("audit/record-outcome failed in send_message finally")
