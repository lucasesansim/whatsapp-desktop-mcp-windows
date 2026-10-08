"""Small CDP programs with exact-recipient guards and JSON-encoded arguments."""

from __future__ import annotations

import json

# WhatsApp identifiers can be strings or model objects. Never compare display names.
JID_FUNCTION = """
const jid = value => {
    if (typeof value === "string") return value;
    if (!value || typeof value !== "object") return null;
    if (typeof value._serialized === "string") return value._serialized;
    if (typeof value.user === "string" && typeof value.server === "string")
        return value.user + "@" + value.server;
    return null;
};
const activeJid = () => {
    try {
        const col = window.require('WAWebCollections').Chat;
        const chat = col && col.getActive ? col.getActive() : null;
        return chat ? jid(chat.id) : null;
    } catch (_) { return null; }
};
const normalize = text => text.replace(/\\r\\n/g, "\\n").replace(/\\r/g, "\\n");
"""


def active_recipient() -> str:
    return "(() => {" + JID_FUNCTION + "return {activeJid: activeJid()};})()"


def compose_text(recipient: str, body: str) -> str:
    return "(() => {" + JID_FUNCTION + """
        const target = """ + json.dumps(recipient) + """;
        const body = """ + json.dumps(body) + """;
        if (activeJid() !== target) return false;
        const input = document.querySelector("#main footer div[contenteditable='true']");
        if (!input || (input.innerText || input.textContent || "").length !== 0) return false;
        // Never append to a draft or send a reply/attachment preview left by the user.
        if (document.querySelector("#main [data-testid='quoted-message'], #main [data-testid='media-preview']"))
            return false;
        input.focus();
        const inserted = document.execCommand('insertText', false, body);
        return inserted !== false && normalize(input.innerText || input.textContent || "") === normalize(body);
    })()"""


def click_send(
    recipient: str, body: str, *, attachment: bool = False,
    filename: str | None = None, size: int | None = None,
) -> str:
    return "(() => {" + JID_FUNCTION + """
        const target = """ + json.dumps(recipient) + """;
        const body = """ + json.dumps(body) + """;
        const attachment = """ + json.dumps(attachment) + """;
        const filename = """ + json.dumps(filename) + """;
        const size = """ + json.dumps(size) + """;
        // Recheck in the same JavaScript task as the click. No Enter-key fallback.
        if (activeJid() !== target) return false;
        if (attachment) {
            // Missing/stale/extra file metadata must block the send.
            const files = Array.from(document.querySelectorAll('input[type="file"]'))
                .flatMap(element => Array.from(element.files || []));
            if (typeof filename !== "string" || !Number.isSafeInteger(size) || size < 0 ||
                files.length !== 1 || files[0].name !== filename || files[0].size !== size)
                return false;
        }
        const input = attachment
            ? document.querySelector('div[contenteditable="true"][aria-label="Digite uma mensagem"]')
            : document.querySelector("#main footer div[contenteditable='true']");
        if ((!input && body !== "") || (input && normalize(input.innerText || input.textContent || "") !== normalize(body)))
            return false;
        const selector = attachment
            ? '[data-icon="wds-ic-send-filled"], [aria-label*="Enviar 1 item selecionado"], [data-icon="send"]'
            : "#main footer span[data-icon='send'], #main footer button[aria-label='Send'], #main footer button[aria-label='Enviar']";
        const icon = document.querySelector(selector);
        const button = icon && (icon.closest("button") || icon.closest('[role="button"]') || icon);
        if (!button || button.disabled || button.getAttribute("aria-disabled") === "true") return false;
        button.click();
        return true;
    })()"""


def outgoing_snapshot(recipient: str, since: int) -> str:
    return "(async () => {" + JID_FUNCTION + """
        const target = """ + json.dumps(recipient) + """;
        const since = """ + json.dumps(since) + """;
        return new Promise((resolve, reject) => {
            const req = window.indexedDB.open("model-storage");
            req.onsuccess = () => {
                const db = req.result;
                let tx;
                try { tx = db.transaction("message", "readonly"); }
                catch (error) { db.close(); reject(error); return; }
                const rows = [];
                let overflow = false;
                const request = tx.objectStore("message").openCursor();
                request.onsuccess = () => {
                    const cursor = request.result;
                    if (!cursor) { db.close(); resolve({rows, overflow}); return; }
                    const m = cursor.value;
                    const id = jid(m.id);
                    const serialized = typeof id === "string" ? id : null;
                    const parts = serialized ? serialized.split("_") : [];
                    const to = jid(m.to) || jid(m.id && m.id.remote) || (parts[0] === "true" ? parts[1] : null);
                    const fromMe = typeof m.fromMe === "boolean" ? m.fromMe
                        : (m.id && typeof m.id.fromMe === "boolean" ? m.id.fromMe : parts[0] === "true");
                    if (to === target && fromMe === true && typeof m.t === "number" && m.t >= since) {
                        let live = null;
                        try { live = window.require('WAWebCollections').Msg.get(m.id); } catch (_) {}
                        if (rows.length >= 2000) overflow = true;
                        else rows.push({
                            id: serialized, to, fromMe, t: m.t, type: m.type,
                            body: typeof m.body === "string" ? m.body : live && live.body,
                            caption: typeof m.caption === "string" ? m.caption : ((live && live.caption) || ""),
                            filename: m.filename || m.fileName || (live && (live.filename || live.fileName)),
                            size: typeof m.size === "number" ? m.size : live && live.size
                        });
                    }
                    cursor.continue();
                };
                request.onerror = () => { db.close(); reject(request.error); };
                tx.onabort = () => { db.close(); reject(tx.error || new Error("Snapshot aborted")); };
            };
            req.onerror = () => reject(req.error);
        });
    })()"""
