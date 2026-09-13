"""``send_file`` MCP tool for sending attachments via WhatsApp Desktop on Windows."""

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
from whatsapp_desktop_mcp.models.send import ConfirmationSchema, SendFileResult
from whatsapp_desktop_mcp.paths import get_audit_log_path
from whatsapp_desktop_mcp.sender import rate_limit
from whatsapp_desktop_mcp.sender.audit import (
    AuditEntry,
    append_audit_entry,
    hash_body,
    hash_file,
)
from whatsapp_desktop_mcp.server import mcp
from whatsapp_desktop_mcp.tools._decorators import timeout

logger = logging.getLogger(__name__)


def _build_file_elicitation_message(
    *,
    chat_name: str,
    chat_id: int,
    recipient_jid: Jid,
    file_name: str,
    file_size_bytes: int,
    caption: str,
    rate_min_rem: int,
    rate_day_rem: int,
) -> str:
    caption_part = f"\nCaption:\n---\n{caption}\n---\n" if caption else "\nCaption: (none)\n"
    return (
        f"Send this attachment via WhatsApp Desktop?\n\n"
        f"Chat: {chat_name}  (id={chat_id}, jid={recipient_jid.raw} kind={recipient_jid.kind})\n"
        f"File: {file_name} ({file_size_bytes:,} bytes)"
        f"{caption_part}"
        f"Rate budget: {rate_min_rem}/min, {rate_day_rem}/day remaining."
    )


@mcp.tool(
    name="send_file",
    title="Send a WhatsApp file attachment (PDF, image, document)",
    description=(
        "Sends a file attachment (such as a PDF report, image, spreadsheet or document) "
        "with an optional caption to one resolved chat (by opaque chat_id from list_chats / "
        "search_contacts). Automatically focuses and opens the conversation in WhatsApp Desktop. "
        "Gated by an MCP elicitation prompt showing resolved chat name, recipient JID, file details, "
        "and caption. Conservative rate limits apply (5/min, 30/day). WhatsApp's Terms of Service "
        "prohibit automated / bulk messaging; use sparingly."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
    meta={"anthropic/maxResultSizeChars": 60_000},
)
@timeout(seconds=25)
async def send_file(
    chat_id: int,
    file_path: str,
    caption: str = "",
    ctx: Context = None,  # type: ignore[type-arg, assignment]
) -> SendFileResult:
    """Send one file attachment with optional caption via WhatsApp Desktop on Windows."""
    send_started_unix = time.time()
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

    resolved_path = os.path.abspath(file_path)
    file_name = os.path.basename(resolved_path)
    file_size = 0
    file_sha = ""
    caption_sha = hash_body(caption)

    try:
        # STEP 1: read_only_mode check
        if server.read_only_mode:
            raise ReadOnlyModeError(
                "Server started with --read-only. To enable sends, restart with --no-read-only."
            )

        # STEP 2: File existence & size validation
        if not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"Attachment file not found: {resolved_path}")

        file_size = os.path.getsize(resolved_path)
        if file_size > 100 * 1024 * 1024:
            raise ValueError(f"File size {file_size} exceeds 100MB limit.")
        file_sha = hash_file(resolved_path)

        # STEP 3: chat_id validation
        chat = await server.reader.find_chat_by_id(chat_id)
        if chat is None:
            raise InvalidChatId(
                f"chat_id={chat_id} does not resolve to any chat in the local DB. "
                f"Use search_contacts or list_chats to discover valid chat_ids."
            )
        chat_name = chat.display_name
        recipient_jid_str = chat.jid.raw

        # STEP 4: rate-limit check
        rate_min_rem, rate_day_rem = await rate_limit.check_and_reserve()

        # STEP 5: MCP elicitation
        if os.environ.get("WHATSAPP_DESKTOP_MCP_SKIP_CONFIRM") == "1":
            confirm_skipped = True
        elif ctx is not None:
            prompt = _build_file_elicitation_message(
                chat_name=chat_name,
                chat_id=chat_id,
                recipient_jid=chat.jid,
                file_name=file_name,
                file_size_bytes=file_size,
                caption=caption,
                rate_min_rem=rate_min_rem,
                rate_day_rem=rate_day_rem,
            )
            try:
                elicit_result = await ctx.elicit(prompt, schema=ConfirmationSchema)
            except Exception as exc:
                await rate_limit.rollback()
                outcome = "error"
                err_msg = f"Elicitation failed: {exc}"
                raise RuntimeError(err_msg) from exc

            if isinstance(elicit_result, (DeclinedElicitation, CancelledElicitation)):
                await rate_limit.rollback()
                outcome = "cancelled"
                return SendFileResult(
                    status="cancelled",
                    chat_id=chat_id,
                    chat_name=chat_name,
                    file_name=file_name,
                    file_size_bytes=file_size,
                    caption=caption or None,
                    rate_limit_remaining_per_min=rate_min_rem,
                    rate_limit_remaining_per_day=rate_day_rem,
                    audit_log_path=audit_log_path,
                    elapsed_ms=int((time.time() - send_started_unix) * 1000),
                )

            if isinstance(elicit_result, AcceptedElicitation):
                action = elicit_result.action
                user_confirmed = getattr(action, "confirm", None) if action else None
                if not user_confirmed:
                    await rate_limit.rollback()
                    outcome = "cancelled"
                    return SendFileResult(
                        status="cancelled",
                        chat_id=chat_id,
                        chat_name=chat_name,
                        file_name=file_name,
                        file_size_bytes=file_size,
                        caption=caption or None,
                        rate_limit_remaining_per_min=rate_min_rem,
                        rate_limit_remaining_per_day=rate_day_rem,
                        audit_log_path=audit_log_path,
                        elapsed_ms=int((time.time() - send_started_unix) * 1000),
                    )

        # STEP 6: Execute send_file via transport
        try:
            is_experimental, send_started_unix_ts = await server.transport.send_file(
                chat,
                resolved_path,
                caption,
            )
        except ChatHeaderMismatch:
            await rate_limit.rollback()
            outcome = "error"
            raise
        except Exception as exc:
            await rate_limit.rollback()
            outcome = "error"
            err_msg = str(exc)
            raise RuntimeError(f"Transport send_file failed: {exc}") from exc

        # STEP 7: Verify outgoing
        message_id = await server.transport.verify_outgoing(
            chat,
            caption or file_name,
            send_started_unix_ts,
            timeout_seconds=12.0,
        )

        if message_id:
            outcome = "sent"
        else:
            outcome = "sent_unverified"
            verification_note = (
                "File send command completed, but outgoing message was not confirmed "
                "in model-storage within 12 seconds. It may still deliver."
            )

        return SendFileResult(
            status=outcome,
            message_id=message_id,
            chat_id=chat_id,
            chat_name=chat_name,
            file_name=file_name,
            file_size_bytes=file_size,
            caption=caption or None,
            verification_note=verification_note,
            rate_limit_remaining_per_min=rate_min_rem,
            rate_limit_remaining_per_day=rate_day_rem,
            audit_log_path=audit_log_path,
            elapsed_ms=int((time.time() - send_started_unix) * 1000),
            is_experimental=is_experimental,
            confirm_skipped=confirm_skipped,
        )

    except RateLimitExceeded:
        outcome = "rate_limited"
        raise
    except (ReadOnlyModeError, InvalidChatId, ChatHeaderMismatch, SendTimeout, FileNotFoundError):
        outcome = "error"
        raise
    except Exception as exc:
        outcome = "error"
        err_msg = str(exc)
        raise
    finally:
        elapsed = int((time.time() - send_started_unix) * 1000)
        entry = AuditEntry(
            ts=int(send_started_unix),
            chat_id=chat_id,
            recipient_jid=recipient_jid_str,
            body_sha256=caption_sha,
            file_sha256=file_sha or None,
            file_name=file_name if file_size > 0 else None,
            outcome=outcome,
            message_id=message_id,
            rate_limit_remaining_per_min=rate_min_rem,
            rate_limit_remaining_per_day=rate_day_rem,
            elapsed_ms=elapsed,
            confirm_skipped=confirm_skipped,
            error_message=err_msg,
        )
        try:
            await append_audit_entry(entry)
        except Exception as audit_exc:
            logger.error("Failed to append audit entry for send_file: %s", audit_exc)
