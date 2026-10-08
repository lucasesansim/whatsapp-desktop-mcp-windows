"""Windows WhatsApp send transport via Chrome DevTools Protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os

from whatsapp_desktop_mcp.exceptions import ChatHeaderMismatch
from whatsapp_desktop_mcp.interfaces.transport import WhatsAppTransport
from whatsapp_desktop_mcp.models.chat import Chat
from whatsapp_desktop_mcp.time import now_unix
from whatsapp_desktop_mcp.windows import scripts
from whatsapp_desktop_mcp.windows.cdp_client import CDPClient
from whatsapp_desktop_mcp.windows.verification import PendingSend, validate_jid

logger = logging.getLogger(__name__)

class WindowsCDPTransport(WhatsAppTransport):
    """Transport driving the Windows WhatsApp Desktop WebView2 via CDP."""

    def __init__(self, cdp_client: CDPClient) -> None:
        self.cdp = cdp_client
        self._pending: PendingSend | None = None

    async def _ensure_connected(self) -> None:
        await self.cdp.connect()

    async def open_chat(self, chat: Chat) -> bool:
        """Ensure the target conversation is actively open and focused in the WhatsApp UI."""
        await self._ensure_connected()
        jid_raw = validate_jid(chat.jid.raw)
        js_open = f"""
        (async () => {{
            try {{
                const chatCol = window.require('WAWebCollections').Chat;
                const cmd = window.require('WAWebCmd').Cmd;
                let model = chatCol.get({json.dumps(jid_raw)});
                if (!model && chatCol.find) {{
                    try {{ model = await chatCol.find({json.dumps(jid_raw)}); }} catch(e) {{}}
                }}
                if (!model) {{
                    const models = chatCol.getModelsArray ? chatCol.getModelsArray() : (chatCol._models || chatCol.models || []);
                    model = models.find(m => String(m.id || "") === {json.dumps(jid_raw)});
                }}
                if (!model) return false;
                cmd.openChatBottom({{ chat: model }});
                return true;
            }} catch(e) {{
                return false;
            }}
        }})()
        """
        opened = await self.cdp.evaluate(js_open)
        if opened:
            await asyncio.sleep(0.7)
        return bool(opened)

    async def assert_recipient(self, chat: Chat) -> None:
        """Accept only the exact active identifier, never a name or substring."""
        await self._ensure_connected()
        expected = validate_jid(chat.jid.raw)
        info = await self.cdp.evaluate(scripts.active_recipient()) or {}
        if info.get("activeJid") != expected:
            if await self.open_chat(chat):
                info = await self.cdp.evaluate(scripts.active_recipient()) or {}
        if info.get("activeJid") != expected:
            raise ChatHeaderMismatch("The exact recipient could not be verified; send blocked.")

    async def _snapshot(self, recipient: str, since: int) -> list[dict]:
        result = await self.cdp.evaluate(scripts.outgoing_snapshot(recipient, since))
        if not isinstance(result, dict) or result.get("overflow") is not False:
            raise RuntimeError("Cannot establish a complete outgoing-message snapshot.")
        rows = result.get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise RuntimeError("Unexpected outgoing-message snapshot.")
        return rows

    async def _begin_send(
        self, chat: Chat, body: str, *, filename: str | None = None, size: int | None = None
    ) -> int:
        self._pending = None
        recipient = validate_jid(chat.jid.raw)
        started = now_unix()
        rows = await self._snapshot(recipient, started - 5)
        self._pending = PendingSend(
            recipient=recipient, body=body, started=started,
            previous_ids={row["id"] for row in rows if isinstance(row.get("id"), str)},
            filename=filename, size=size,
        )
        return started

    async def send_text(self, chat: Chat, body: str) -> tuple[bool, int]:
        """Refuse draft contamination and recheck identity atomically with the click."""
        if not isinstance(body, str) or not body.strip() or "\x00" in body:
            raise ValueError("Message must contain non-empty text without NUL characters.")
        await self._ensure_connected()
        await self.assert_recipient(chat)
        started = await self._begin_send(chat, body)
        if await self.cdp.evaluate(scripts.compose_text(chat.jid.raw, body)) is not True:
            raise RuntimeError("Composer is unavailable, changed, or already contains a draft.")
        if await self.cdp.evaluate(scripts.click_send(chat.jid.raw, body)) is not True:
            raise ChatHeaderMismatch(
                "Recipient, composer, or send button changed; send blocked. Inspect the draft."
            )
        return chat.kind == "group", started

    async def send_file(
        self,
        chat: Chat,
        file_path: str,
        caption: str = "",
    ) -> tuple[bool, int]:
        """Send a file (PDF, image, document) to the verified chat.

        Returns (is_experimental, send_started_unix_ts).
        """
        await self._ensure_connected()
        is_experimental = chat.kind == "group"

        resolved_path = os.path.abspath(file_path)
        if not os.path.isfile(resolved_path):
            raise FileNotFoundError(f"File not found: {resolved_path}")

        file_size = os.path.getsize(resolved_path)
        if file_size > 100 * 1024 * 1024:
            raise ValueError(f"File size {file_size} exceeds maximum 100MB limit.")

        file_name = os.path.basename(resolved_path)
        mime_type, _ = mimetypes.guess_type(resolved_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Step 1: Assert recipient (auto-opens conversation if needed)
        await self.assert_recipient(chat)
        draft_clear = await self.cdp.evaluate(scripts.compose_text(chat.jid.raw, ""))
        if draft_clear is not True:
            raise RuntimeError("An existing draft or preview blocks file sending.")
        start_ts = await self._begin_send(
            chat, caption, filename=file_name, size=file_size
        )

        # Step 2: Open attachment menu ("Anexar" button)
        js_open_attach = """
        (() => {
            const attachBtn = document.querySelector(
                '#main footer button[aria-label="Anexar"], #main footer [data-icon="plus-rounded"]'
            );
            if (!attachBtn) return false;
            (attachBtn.closest('button') || attachBtn).click();
            return true;
        })()
        """
        opened_menu = await self.cdp.evaluate(js_open_attach)
        if not opened_menu:
            raise RuntimeError("Could not locate or click the attachment '+' button in WhatsApp footer.")

        await asyncio.sleep(0.4)

        # Step 3: Click "Documento" menu item to ensure high-resolution / document attachment
        js_click_doc = """
        (() => {
            const spans = Array.from(document.querySelectorAll('span, div'));
            const docEl = spans.find(s => s.innerText && s.innerText.trim() === 'Documento');
            if (!docEl) return false;
            const clickTarget = docEl.closest('button') || docEl.closest('li') || docEl.parentElement;
            clickTarget.click();
            return true;
        })()
        """
        clicked_doc = await self.cdp.evaluate(js_click_doc)
        if not clicked_doc:
            raise RuntimeError("Could not find or click 'Documento' in the attachment menu.")

        await asyncio.sleep(0.4)

        # Step 4: Locate the document file input element and acquire its CDP objectId
        js_get_input = """
        document.querySelector('input[accept="*"]') ||
        document.querySelectorAll('input[type="file"]')[1] ||
        document.querySelector('input[type="file"]')
        """
        input_eval = await self.cdp.send(
            "Runtime.evaluate",
            {"expression": js_get_input, "returnByValue": False},
        )
        obj_id = input_eval.get("result", {}).get("objectId")
        if not obj_id:
            raise RuntimeError("Failed to resolve file input element objectId in WhatsApp Web.")

        # Step 5: Inject file via native CDP DOM.setFileInputFiles
        await self.cdp.send(
            "DOM.setFileInputFiles",
            {"files": [resolved_path], "objectId": obj_id},
        )

        # Step 6: Wait for document preview stage to appear (up to 6 seconds)
        js_check_preview = """
        (() => {
            const sendBtn = document.querySelector(
                '[data-icon="wds-ic-send-filled"], [aria-label*="Enviar 1 item selecionado"], [data-icon="send"]'
            );
            const captionInput = document.querySelector(
                'div[contenteditable="true"][aria-label="Digite uma mensagem"]'
            );
            return { hasSendBtn: !!sendBtn, hasCaption: !!captionInput };
        })()
        """
        stage_ready = False
        for _ in range(20):
            await asyncio.sleep(0.3)
            info = await self.cdp.evaluate(js_check_preview) or {}
            if info.get("hasSendBtn"):
                stage_ready = True
                break

        if not stage_ready:
            raise RuntimeError("WhatsApp media preview stage did not appear after file selection.")

        # Step 7: If caption provided, type it into the document preview caption composer
        if caption:
            js_caption = f"""
            (() => {{
                const captionInput = document.querySelector(
                    'div[contenteditable="true"][aria-label="Digite uma mensagem"]'
                ) || Array.from(document.querySelectorAll('div[contenteditable="true"]')).find(
                    el => el.getAttribute('aria-label') === 'Digite uma mensagem'
                );
                if (captionInput) {{
                    captionInput.focus();
                    document.execCommand('insertText', false, {json.dumps(caption)});
                    return true;
                }}
                return false;
            }})()
            """
            await self.cdp.evaluate(js_caption)
            await asyncio.sleep(0.3)

        # Recheck recipient and exact caption in the same task as the send click.
        if await self.cdp.evaluate(
            scripts.click_send(
                chat.jid.raw, caption, attachment=True, filename=file_name, size=file_size
            )
        ) is not True:
            raise ChatHeaderMismatch("Attachment recipient, selected file, or caption changed; send blocked.")

        # Step 9: Wait for preview stage to close
        for _ in range(15):
            await asyncio.sleep(0.3)
            info = await self.cdp.evaluate(js_check_preview) or {}
            if not info.get("hasSendBtn"):
                break

        return is_experimental, start_ts

    async def verify_outgoing(
        self,
        chat: Chat,
        body: str,
        start_ts: int,
        timeout_seconds: float = 10.0,
    ) -> str | None:
        """Observe a new, exact local record; this is not a delivery receipt."""
        pending = self._pending
        if pending is None or pending.recipient != chat.jid.raw or pending.started != start_ts:
            raise RuntimeError("No matching send attempt is available for verification.")
        if pending.filename is None and pending.body != body:
            raise RuntimeError("Verification text differs from the send attempt.")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_seconds
        try:
            while True:
                rows = await self._snapshot(pending.recipient, pending.started)
                matches = [message_id for row in rows if (message_id := pending.match(row))]
                # More than one identical new record is ambiguous.
                if len(set(matches)) == 1:
                    return matches[0]
                if len(set(matches)) > 1 or loop.time() >= deadline:
                    return None
                await asyncio.sleep(min(0.2, max(0, deadline - loop.time())))
        finally:
            self._pending = None
