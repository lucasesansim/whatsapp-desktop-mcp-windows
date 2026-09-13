"""Windows WhatsApp send transport via Chrome DevTools Protocol."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import os

from whatsapp_desktop_mcp.exceptions import ChatHeaderMismatch
from whatsapp_desktop_mcp.interfaces.transport import WhatsAppTransport
from whatsapp_desktop_mcp.models.chat import Chat
from whatsapp_desktop_mcp.time import now_unix
from whatsapp_desktop_mcp.windows.cdp_client import CDPClient

logger = logging.getLogger(__name__)

# Bidi control characters to strip
_BIDI_CHARS = ["\u200e", "\u2068", "\u2069"]


def _strip_bidi(text: str) -> str:
    res = text
    for ch in _BIDI_CHARS:
        res = res.replace(ch, "")
    return res.strip()


class WindowsCDPTransport(WhatsAppTransport):
    """Transport driving the Windows WhatsApp Desktop WebView2 via CDP."""

    def __init__(self, cdp_client: CDPClient) -> None:
        self.cdp = cdp_client

    async def _ensure_connected(self) -> None:
        await self.cdp.connect()

    async def open_chat(self, chat: Chat) -> bool:
        """Ensure the target conversation is actively open and focused in the WhatsApp UI."""
        await self._ensure_connected()
        jid_raw = chat.jid.raw
        js_open = f"""
        (async () => {{
            try {{
                const chatCol = window.require('WAWebCollections').Chat;
                const cmd = window.require('WAWebCmd').Cmd;
                let model = chatCol.get("{jid_raw}");
                if (!model && chatCol.find) {{
                    try {{ model = await chatCol.find("{jid_raw}"); }} catch(e) {{}}
                }}
                if (!model) {{
                    const models = chatCol.getModelsArray ? chatCol.getModelsArray() : (chatCol._models || chatCol.models || []);
                    model = models.find(m => String(m.id || "") === "{jid_raw}");
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
        """Verify that the active conversation in WhatsApp matches chat, auto-opening if needed."""
        await self._ensure_connected()
        jid_raw = chat.jid.raw

        js_check = f"""
        (() => {{
            const chatCol = window.require ? window.require('WAWebCollections').Chat : null;
            const activeChat = chatCol && chatCol.getActive ? chatCol.getActive() : null;
            const activeJid = activeChat ? String(activeChat.id || '') : null;

            const header = document.querySelector("#main header");
            const titleEl = header ? header.querySelector("span[title], div[title]") : null;
            const headerTitle = titleEl ? titleEl.getAttribute("title") : (header ? header.innerText.split('\\n')[0] : null);

            return {{
                activeJid: activeJid,
                headerTitle: headerTitle,
                isMatchJid: activeJid === "{jid_raw}"
            }};
        }})()
        """
        info = await self.cdp.evaluate(js_check) or {}
        is_match = info.get("isMatchJid")

        if not is_match:
            # Try to auto-open the chat for a fluid workflow
            opened = await self.open_chat(chat)
            if opened:
                info = await self.cdp.evaluate(js_check) or {}
                is_match = info.get("isMatchJid")

        active_title = info.get("headerTitle")
        if not is_match and not active_title:
            raise ChatHeaderMismatch(
                f"No active chat conversation open in WhatsApp UI. Expected: '{chat.display_name}'"
            )

        clean_expected = _strip_bidi(chat.display_name).casefold()
        clean_active = _strip_bidi(active_title or "").casefold()

        if not is_match and (clean_expected not in clean_active and clean_active not in clean_expected):
            raise ChatHeaderMismatch(
                f"Active chat header mismatch! Expected '{chat.display_name}', but active is '{active_title}'."
            )

    async def send_text(self, chat: Chat, body: str) -> tuple[bool, int]:
        """Send message text to the verified chat.

        Returns (is_experimental, send_started_unix_ts).
        """
        await self._ensure_connected()
        start_ts = now_unix()
        is_experimental = chat.kind == "group"

        # Step 1: Assert recipient
        await self.assert_recipient(chat)

        # Step 2: Focus the compose box and type text
        js_type = f"""
        (() => {{
            const input = document.querySelector("#main footer div[contenteditable='true']");
            if (!input) return false;
            input.focus();
            document.execCommand('insertText', false, {json.dumps(body)});
            return true;
        }})()
        """

        inserted = await self.cdp.evaluate(js_type)
        if not inserted:
            raise RuntimeError("Could not locate or focus the WhatsApp compose input field.")

        await asyncio.sleep(0.3)

        # Step 3: Click send button or dispatch Enter
        js_click_send = """
        (() => {
            const sendBtn = document.querySelector("#main footer span[data-icon='send']") ||
                            document.querySelector("#main footer button[aria-label='Send']") ||
                            document.querySelector("#main footer button[aria-label='Enviar']");
            if (sendBtn) {
                const btn = sendBtn.closest("button") || sendBtn;
                btn.click();
                return true;
            }
            return false;
        })()
        """
        clicked = await self.cdp.evaluate(js_click_send)
        if not clicked:
            # Fallback to Enter key via CDP Input domain
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyDown",
                    "windowsVirtualKeyCode": 13,
                    "nativeVirtualKeyCode": 13,
                    "text": "\r",
                },
            )
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13},
            )

        return is_experimental, start_ts

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
        start_ts = now_unix()
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

        with open(resolved_path, "rb") as f:
            file_bytes = f.read()

        b64_content = base64.b64encode(file_bytes).decode("ascii")

        # Step 1: Assert recipient (auto-opens conversation if needed)
        await self.assert_recipient(chat)

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

        # Step 8: Click send button or dispatch Enter
        js_click_send = """
        (() => {
            const sendBtn = document.querySelector(
                '[data-icon="wds-ic-send-filled"], [aria-label*="Enviar 1 item selecionado"], [data-icon="send"]'
            );
            if (sendBtn) {
                (sendBtn.closest('button') || sendBtn.closest('[role="button"]') || sendBtn).click();
                return true;
            }
            return false;
        })()
        """
        clicked = await self.cdp.evaluate(js_click_send)
        if not clicked:
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyDown",
                    "windowsVirtualKeyCode": 13,
                    "nativeVirtualKeyCode": 13,
                    "text": "\\r",
                },
            )
            await self.cdp.send(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 13},
            )

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
        """Poll model-storage for the recorded outgoing message."""
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        jid_raw = chat.jid.raw

        js_poll = f"""
        (async () => {{
            return new Promise((resolve) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("message", "readonly");
                    const store = tx.objectStore("message");
                    const cursorReq = store.openCursor(null, "prev"); // newest first
                    const targetJid = "{jid_raw}";

                    cursorReq.onsuccess = (ev) => {{
                        const cur = ev.target.result;
                        if (cur) {{
                            const m = cur.value;
                            const mId = String(m.id || "");
                            if (mId.startsWith("true_") && (mId.includes(targetJid) || m.to === targetJid)) {{
                                if ((m.t || 0) >= {start_ts - 5}) {{
                                    db.close();
                                    resolve(m.id);
                                    return;
                                }}
                            }}
                            cur.continue();
                        }} else {{
                            db.close();
                            resolve(null);
                        }}
                    }};
                    cursorReq.onerror = () => {{ db.close(); resolve(null); }};
                }};
                req.onerror = () => resolve(null);
            }});
        }})()
        """
        while asyncio.get_event_loop().time() < deadline:
            try:
                msg_id = await self.cdp.evaluate(js_poll)
                if msg_id:
                    return str(msg_id)
            except Exception as exc:
                logger.debug("Verify outgoing poll error: %s", exc)
            await asyncio.sleep(0.5)

        return None
