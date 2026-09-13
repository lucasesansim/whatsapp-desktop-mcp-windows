"""IndexedDB reader implementation over Chrome DevTools Protocol."""

from __future__ import annotations

import logging
from typing import Any

from whatsapp_desktop_mcp.interfaces.reader import WhatsAppReader
from whatsapp_desktop_mcp.models.chat import Chat, ChatKind
from whatsapp_desktop_mcp.models.contact import Contact, Jid
from whatsapp_desktop_mcp.models.coverage import Coverage
from whatsapp_desktop_mcp.models.cursor import decode_cursor, encode_cursor
from whatsapp_desktop_mcp.models.group import GroupInfo, GroupMember
from whatsapp_desktop_mcp.models.media import MediaRef
from whatsapp_desktop_mcp.models.message import Message, MessageKind
from whatsapp_desktop_mcp.time import now_unix
from whatsapp_desktop_mcp.windows.cdp_client import CDPClient

logger = logging.getLogger(__name__)


def _extract_msg_id(val: Any) -> str:
    if isinstance(val, dict):
        return str(val.get("_serialized") or val.get("$1") or val.get("id") or "")
    return str(val or "")


def _extract_quoted_msg_id(val: Any) -> str | None:
    if not val:
        return None
    if isinstance(val, dict):
        res = val.get("_serialized") or val.get("$1") or val.get("id")
        return str(res) if res else None
    return str(val)


def _jid_to_chat_id(jid_raw: str) -> int:
    """Generate a stable positive integer chat_id from a JID string."""
    import hashlib

    digest = hashlib.md5(jid_raw.encode("utf-8")).hexdigest()
    # 31-bit positive int
    return int(digest[:8], 16) & 0x7FFFFFFF


def _map_chat_kind(jid_raw: str) -> ChatKind:
    if jid_raw.endswith("@g.us"):
        return "group"
    elif jid_raw.endswith("@broadcast"):
        return "broadcast"
    elif "community" in jid_raw:
        return "community"
    return "direct"


def _map_message_kind(raw_type: str | None) -> MessageKind:
    t = str(raw_type or "").lower()
    mapping: dict[str, MessageKind] = {
        "chat": "text",
        "text": "text",
        "image": "image",
        "video": "video",
        "audio": "audio",
        "ptt": "audio",
        "system": "system",
        "location": "location",
        "vcard": "contact",
        "contact": "contact",
        "sticker": "sticker",
        "call_log": "call",
        "revoked": "revoked",
        "ephemeral": "ephemeral",
        "poll_creation": "poll",
        "reaction": "reaction",
    }
    return mapping.get(t, "other")


class IndexedDBReader(WhatsAppReader):
    """Reads WhatsApp Desktop history directly from model-storage IndexedDB via CDP."""

    def __init__(self, cdp_client: CDPClient) -> None:
        self.cdp = cdp_client
        self._chat_cache: dict[int, str] = {}  # chat_id -> jid_raw
        self._jid_cache: dict[str, int] = {}  # jid_raw -> chat_id

    async def _ensure_connected(self) -> None:
        await self.cdp.connect()

    async def list_chats(self, limit: int = 200) -> list[Chat]:
        await self._ensure_connected()
        js_code = f"""
        (async () => {{
            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("chat", "readonly");
                    const store = tx.objectStore("chat");
                    const chats = [];
                    const cursorReq = store.openCursor();
                    cursorReq.onsuccess = (ev) => {{
                        const cursor = ev.target.result;
                        if (cursor) {{
                            const val = cursor.value;
                            if (val && val.id) {{
                                chats.push({{
                                    id: val.id,
                                    name: val.name || val.formattedTitle || val.pushname || val.id.split('@')[0],
                                    t: val.t || 0,
                                    unreadCount: val.unreadCount || 0,
                                    archive: !!val.archive,
                                    isLocked: !!val.isLocked,
                                    mute: !!val.isAutoMuted
                                }});
                            }}
                            cursor.continue();
                        }} else {{
                            chats.sort((a, b) => (b.t || 0) - (a.t || 0));
                            db.close();
                            resolve(chats.slice(0, {limit}));
                        }}
                    }};
                    cursorReq.onerror = () => {{ db.close(); reject(cursorReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        raw_chats = await self.cdp.evaluate(js_code) or []
        result: list[Chat] = []

        for item in raw_chats:
            jid_raw = str(item.get("id"))
            c_id = _jid_to_chat_id(jid_raw)
            self._chat_cache[c_id] = jid_raw
            self._jid_cache[jid_raw] = c_id

            t = item.get("t")
            coverage = Coverage(
                from_ts=t,
                to_ts=now_unix(),
                asked_window_seconds=None,
                have_window_seconds=None,
                is_full=True,
            )
            chat = Chat(
                chat_id=c_id,
                kind=_map_chat_kind(jid_raw),
                jid=Jid.from_raw(jid_raw),
                display_name=item.get("name") or jid_raw.split("@")[0],
                last_activity_ts=t,
                last_message_preview=None,
                unread_count=item.get("unreadCount", 0),
                is_archived=item.get("archive", False),
                is_hidden=item.get("isLocked", False),
                coverage=coverage,
            )
            result.append(chat)
        return result

    async def find_chat_by_id(self, chat_id: int) -> Chat | None:
        jid = self._chat_cache.get(chat_id)
        if jid:
            return await self.find_chat_by_jid(jid)
        # Search all chats
        all_chats = await self.list_chats(limit=500)
        for c in all_chats:
            if c.chat_id == chat_id:
                return c
        return None

    async def find_chat_by_jid(self, jid_raw: str) -> Chat | None:
        await self._ensure_connected()
        js_code = f"""
        (async () => {{
            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("chat", "readonly");
                    const store = tx.objectStore("chat");
                    const getReq = store.get("{jid_raw}");
                    getReq.onsuccess = () => {{
                        const val = getReq.result;
                        db.close();
                        if (!val) resolve(null);
                        else {{
                            let title = val.name || val.formattedTitle || val.pushname;
                            if (!title || /^\\d+$/.test(title)) {{
                                try {{
                                    const col = window.require ? window.require('WAWebCollections').Chat : null;
                                    const c = col ? col.get(val.id) : null;
                                    if (c && c.formattedTitle) title = c.formattedTitle;
                                    else if (c && c.contact && (c.contact.name || c.contact.formattedName)) {{
                                        title = c.contact.name || c.contact.formattedName;
                                    }}
                                }} catch(e) {{}}
                            }}
                            resolve({{
                                id: val.id,
                                name: title || val.id.split('@')[0],
                                t: val.t || 0,
                                unreadCount: val.unreadCount || 0,
                                archive: !!val.archive,
                                isLocked: !!val.isLocked
                            }});
                        }}
                    }};
                    getReq.onerror = () => {{ db.close(); reject(getReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        val = await self.cdp.evaluate(js_code)
        if not val:
            return None

        c_id = _jid_to_chat_id(jid_raw)
        self._chat_cache[c_id] = jid_raw
        self._jid_cache[jid_raw] = c_id

        return Chat(
            chat_id=c_id,
            kind=_map_chat_kind(jid_raw),
            jid=Jid.from_raw(jid_raw),
            display_name=val.get("name") or jid_raw.split("@")[0],
            last_activity_ts=val.get("t"),
            unread_count=val.get("unreadCount", 0),
            is_archived=val.get("archive", False),
            is_hidden=val.get("isLocked", False),
            coverage=Coverage(from_ts=val.get("t"), to_ts=now_unix(), is_full=True),
        )

    async def read_chat(
        self,
        chat_id: int,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None]:
        chat = await self.find_chat_by_id(chat_id)
        if not chat:
            return [], None

        jid_raw = chat.jid.raw
        cutoff_ts = 999999999999
        if cursor:
            try:
                _, anchor, _ = decode_cursor(cursor)
                cutoff_ts = int(anchor)
            except Exception:
                pass

        await self._ensure_connected()
        js_code = f"""
        (async () => {{
            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = async (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("message", "readonly");
                    const store = tx.objectStore("message");
                    const cursorReq = store.openCursor();
                    const messages = [];
                    const targetJid = "{jid_raw}";
                    const liveMap = new Map();
                    try {{
                        const col = window.require && window.require('WAWebCollections');
                        const chat = col && col.Chat ? col.Chat.get(targetJid) : null;
                        if (chat && typeof chat.getAllMsgs === 'function') {{
                            const msgs = await chat.getAllMsgs();
                            if (msgs) {{
                                for (let i = 0; i < msgs.length; i++) {{
                                    const item = msgs[i];
                                    const sId = item.id ? (item.id._serialized || String(item.id)) : null;
                                    if (sId) liveMap.set(sId, item.body || item.caption || null);
                                }}
                            }}
                        }}
                    }} catch(e) {{}}

                    const getBody = (m) => {{
                        let b = m.body || m.caption || null;
                        if (!b) {{
                            b = liveMap.get(String(m.id)) || null;
                        }}
                        if (!b) {{
                            try {{
                                const col = window.require && window.require('WAWebCollections');
                                if (col && col.Msg) {{
                                    const live = col.Msg.get(m.id);
                                    if (live) b = live.body || live.caption || null;
                                }}
                            }} catch(e) {{}}
                        }}
                        return b;
                    }};

                    cursorReq.onsuccess = (ev) => {{
                        const cur = ev.target.result;
                        if (cur) {{
                            const m = cur.value;
                            const mId = String(m.id || "");
                            const mFrom = String(m.from || "");
                            const mTo = String(m.to || "");
                            if (mId.includes(targetJid) || mFrom === targetJid || mTo === targetJid) {{
                                if ((m.t || 0) < {cutoff_ts}) {{
                                    messages.push({{
                                        id: m.id,
                                        t: m.t || 0,
                                        from: typeof m.from === 'object' ? (m.from._serialized || m.from.user) : m.from,
                                        to: typeof m.to === 'object' ? (m.to._serialized || m.to.user) : m.to,
                                        author: typeof m.author === 'object' ? (m.author._serialized || m.author.user) : m.author,
                                        body: getBody(m),
                                        type: m.type || "chat",
                                        fromMe: mId.startsWith("true_"),
                                        isStarred: !!m.isStarred,
                                        quotedMsgId: m.quotedMsg ? m.quotedMsg.id : null,
                                        mimetype: m.mimetype,
                                        size: m.size
                                    }});
                                }}
                            }}
                            cur.continue();
                        }} else {{
                            messages.sort((a, b) => b.t - a.t);
                            db.close();
                            resolve(messages.slice(0, {limit + 1}));
                        }}
                    }};
                    cursorReq.onerror = () => {{ db.close(); reject(cursorReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        raw_msgs = await self.cdp.evaluate(js_code) or []
        has_more = len(raw_msgs) > limit
        selected_raw = raw_msgs[:limit]

        messages: list[Message] = []
        for rm in selected_raw:
            sender_str = rm.get("author") or rm.get("from") or jid_raw
            media_ref = None
            if rm.get("mimetype"):
                media_ref = MediaRef(
                    local_path="",
                    filename=f"media_{rm.get('id')}",
                    mime=rm.get("mimetype", "application/octet-stream"),
                    size_bytes=rm.get("size") or 0,
                )

            messages.append(
                Message(
                    message_id=_extract_msg_id(rm.get("id")),
                    chat_id=chat_id,
                    sender_jid=Jid.from_raw(str(sender_str)),
                    timestamp=rm.get("t", 0),
                    body=rm.get("body"),
                    kind=_map_message_kind(rm.get("type")),
                    is_outgoing=rm.get("fromMe", False),
                    is_starred=rm.get("isStarred", False),
                    quoted_message_id=_extract_quoted_msg_id(rm.get("quotedMsgId")),
                    media=media_ref,
                )
            )

        next_cursor = None
        if has_more and messages:
            next_cursor = encode_cursor(chat_id, messages[-1].timestamp, "unix_ts")

        return messages, next_cursor

    async def extract_recent(
        self, since_ts: int, chat_id: int | None = None, limit: int = 200
    ) -> list[Message]:
        await self._ensure_connected()
        filter_jid = ""
        if chat_id:
            chat = await self.find_chat_by_id(chat_id)
            if chat:
                filter_jid = chat.jid.raw

        js_code = f"""
        (async () => {{
            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("message", "readonly");
                    const store = tx.objectStore("message");
                    const cursorReq = store.openCursor();
                    const messages = [];
                    const filterJid = "{filter_jid}";

                    cursorReq.onsuccess = (ev) => {{
                        const cur = ev.target.result;
                        if (cur) {{
                            const m = cur.value;
                            if ((m.t || 0) >= {since_ts}) {{
                                const mId = String(m.id || "");
                                const mFrom = typeof m.from === 'object' ? (m.from._serialized || m.from.user) : String(m.from || "");
                                const mTo = typeof m.to === 'object' ? (m.to._serialized || m.to.user) : String(m.to || "");
                                if (!filterJid || mId.includes(filterJid) || mFrom === filterJid || mTo === filterJid) {{
                                    messages.push({{
                                        id: m.id,
                                        t: m.t || 0,
                                        from: mFrom,
                                        to: mTo,
                                        author: typeof m.author === 'object' ? (m.author._serialized || m.author.user) : m.author,
                                        body: m.body || m.caption || null,
                                        type: m.type || "chat",
                                        fromMe: String(m.id || "").startsWith("true_"),
                                        isStarred: !!m.isStarred,
                                        quotedMsgId: m.quotedMsg ? m.quotedMsg.id : null
                                    }});
                                }}
                            }}
                            cur.continue();
                        }} else {{
                            messages.sort((a, b) => a.t - b.t);
                            db.close();
                            resolve(messages.slice(0, {limit}));
                        }}
                    }};
                    cursorReq.onerror = () => {{ db.close(); reject(cursorReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        raw_msgs = await self.cdp.evaluate(js_code) or []
        result: list[Message] = []
        for rm in raw_msgs:
            sender_str = rm.get("author") or rm.get("from") or ""
            target_chat_str = rm.get("from") if not rm.get("fromMe") else rm.get("to")
            c_id = _jid_to_chat_id(str(target_chat_str or ""))
            result.append(
                Message(
                    message_id=_extract_msg_id(rm.get("id")),
                    chat_id=c_id,
                    sender_jid=Jid.from_raw(str(sender_str)),
                    timestamp=rm.get("t", 0),
                    body=rm.get("body"),
                    kind=_map_message_kind(rm.get("type")),
                    is_outgoing=rm.get("fromMe", False),
                    is_starred=rm.get("isStarred", False),
                    quoted_message_id=_extract_quoted_msg_id(rm.get("quotedMsgId")),
                )
            )
        return result

    async def search_messages(
        self,
        query: str,
        chat_id: int | None = None,
        limit: int = 100,
    ) -> list[Message]:
        await self._ensure_connected()
        q_clean = query.replace('"', '\\"').lower()
        filter_jid = ""
        if chat_id:
            chat = await self.find_chat_by_id(chat_id)
            if chat:
                filter_jid = chat.jid.raw

        js_code = f"""
        (async () => {{
            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("message", "readonly");
                    const store = tx.objectStore("message");
                    const cursorReq = store.openCursor();
                    const matches = [];
                    const seen = new Set();
                    const q = "{q_clean}";
                    const filterJid = "{filter_jid}";

                    try {{
                        const col = window.require && window.require('WAWebCollections');
                        if (col && col.Msg) {{
                            const arr = col.Msg._models || (typeof col.Msg.toArray === 'function' ? col.Msg.toArray() : []);
                            for (let i = 0; i < arr.length; i++) {{
                                const m = arr[i];
                                const text = (m.body || m.caption || "").toLowerCase();
                                if (text.includes(q)) {{
                                    const sId = m.id ? (m.id._serialized || String(m.id)) : "";
                                    const sFrom = m.from ? (m.from._serialized || String(m.from)) : "";
                                    const sTo = m.to ? (m.to._serialized || String(m.to)) : "";
                                    if (!filterJid || sId.includes(filterJid) || sFrom.includes(filterJid) || sTo.includes(filterJid)) {{
                                        seen.add(sId);
                                        matches.push({{
                                            id: sId,
                                            t: m.t || 0,
                                            from: sFrom,
                                            to: sTo,
                                            author: m.author ? (m.author._serialized || String(m.author)) : sFrom,
                                            body: m.body || m.caption || null,
                                            type: m.type || "chat",
                                            fromMe: m.id ? !!m.id.fromMe : false,
                                            isStarred: !!m.isStarred
                                        }});
                                    }}
                                }}
                            }}
                        }}
                    }} catch(e) {{}}

                    cursorReq.onsuccess = (ev) => {{
                        const cur = ev.target.result;
                        if (cur) {{
                            const m = cur.value;
                            const mId = String(m.id || "");
                            if (!seen.has(mId)) {{
                                const text = (m.body || m.caption || "").toLowerCase();
                                if (text.includes(q)) {{
                                    if (!filterJid || mId.includes(filterJid)) {{
                                        matches.push({{
                                            id: m.id,
                                            t: m.t || 0,
                                            from: typeof m.from === 'object' ? (m.from._serialized || m.from.user) : m.from,
                                            to: typeof m.to === 'object' ? (m.to._serialized || m.to.user) : m.to,
                                            author: typeof m.author === 'object' ? (m.author._serialized || m.author.user) : m.author,
                                            body: m.body || m.caption || null,
                                            type: m.type || "chat",
                                            fromMe: mId.startsWith("true_"),
                                            isStarred: !!m.isStarred
                                        }});
                                    }}
                                }}
                            }}

                            cur.continue();
                        }} else {{
                            matches.sort((a, b) => b.t - a.t);
                            db.close();
                            resolve(matches.slice(0, {limit}));
                        }}
                    }};
                    cursorReq.onerror = () => {{ db.close(); reject(cursorReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        raw_msgs = await self.cdp.evaluate(js_code) or []
        result: list[Message] = []
        for rm in raw_msgs:
            sender_str = rm.get("author") or rm.get("from") or ""
            target_chat_str = rm.get("from") if not rm.get("fromMe") else rm.get("to")
            c_id = _jid_to_chat_id(str(target_chat_str or ""))
            result.append(
                Message(
                    message_id=_extract_msg_id(rm.get("id")),
                    chat_id=c_id,
                    sender_jid=Jid.from_raw(str(sender_str)),
                    timestamp=rm.get("t", 0),
                    body=rm.get("body"),
                    kind=_map_message_kind(rm.get("type")),
                    is_outgoing=rm.get("fromMe", False),
                    is_starred=rm.get("isStarred", False),
                    quoted_message_id=_extract_quoted_msg_id(rm.get("quotedMsgId")),
                )
            )
        return result

    async def search_contacts(self, query: str, limit: int = 50) -> list[Contact]:
        await self._ensure_connected()
        q_clean = query.replace('"', '\\"').lower()
        js_code = f"""
        (async () => {{
            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("contact", "readonly");
                    const store = tx.objectStore("contact");
                    const cursorReq = store.openCursor();
                    const contacts = [];
                    const q = "{q_clean}";

                    cursorReq.onsuccess = (ev) => {{
                        const cur = ev.target.result;
                        if (cur) {{
                            const c = cur.value;
                            const name = (c.name || c.displayNameLID || c.pushname || "").toLowerCase();
                            const phone = String(c.phoneNumber || "");
                            const jidStr = String(c.id || "").toLowerCase();
                            if (name.includes(q) || phone.includes(q) || jidStr.includes(q)) {{
                                contacts.push({{
                                    id: c.id,
                                    name: c.name || c.displayNameLID || c.pushname || phone || c.id,
                                    phoneNumber: c.phoneNumber || null
                                }});
                            }}
                            cur.continue();
                        }} else {{
                            db.close();
                            resolve(contacts.slice(0, {limit}));
                        }}
                    }};
                    cursorReq.onerror = () => {{ db.close(); reject(cursorReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        raw_contacts = await self.cdp.evaluate(js_code) or []
        result: list[Contact] = []
        for rc in raw_contacts:
            jid_raw = str(rc.get("id"))
            c_id = _jid_to_chat_id(jid_raw)
            result.append(
                Contact(
                    display_name=rc.get("name") or jid_raw,
                    jid=Jid.from_raw(jid_raw, phone=rc.get("phoneNumber")),
                    chat_id=c_id,
                )
            )
        return result

    async def get_chat_metadata(self, chat_id: int) -> GroupInfo | None:
        chat = await self.find_chat_by_id(chat_id)
        if not chat:
            return None
        jid_raw = chat.jid.raw
        if chat.kind != "group":
            return None

        await self._ensure_connected()
        js_code = f"""
        (async () => {{
            try {{
                const col = window.require && window.require('WAWebCollections');
                const gCol = col && col.WAWebGroupMetadataCollection;
                const g = gCol ? gCol.get('{jid_raw}') : null;
                if (g) {{
                    const parts = g.participants ? (g.participants._models || g.participants.models || g.participants) : [];
                    return {{
                        subject: g.subject || "",
                        desc: g.desc || null,
                        creation: g.creation || null,
                        owner: g.owner ? (g.owner._serialized || g.owner) : null,
                        participants: parts.map(p => ({{
                            id: p.id ? (p.id._serialized || p.id) : p,
                            isAdmin: !!p.isAdmin,
                            isSuperAdmin: !!p.isSuperAdmin
                        }}))
                    }};
                }}
            }} catch(e) {{}}

            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("group-metadata", "readonly");
                    const store = tx.objectStore("group-metadata");
                    const getReq = store.get("{jid_raw}");
                    getReq.onsuccess = () => {{
                        const val = getReq.result;
                        db.close();
                        if (!val) resolve(null);
                        else resolve({{
                            subject: val.subject || "",
                            desc: val.desc || null,
                            creation: val.creation || null,
                            owner: typeof val.owner === 'object' ? (val.owner._serialized || val.owner.user) : val.owner,
                            participants: (val.participants || []).map(p => ({{
                                id: typeof p.id === 'object' ? (p.id._serialized || p.id.user) : p.id,
                                isAdmin: p.isAdmin || p.isSuperAdmin || false
                            }}))
                        }});
                    }};
                    getReq.onerror = () => {{ db.close(); reject(getReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        data = await self.cdp.evaluate(js_code)
        if not data:
            return None

        members: list[GroupMember] = []
        for p in data.get("participants", []):
            p_id = str(p.get("id", ""))
            members.append(
                GroupMember(
                    jid=Jid.from_raw(p_id),
                    display_name=p_id.split("@")[0],
                    is_admin=p.get("isAdmin", False),
                )
            )

        return GroupInfo(
            chat_id=chat_id,
            subject=data.get("subject") or chat.display_name,
            description=data.get("desc"),
            creation_ts=data.get("creation"),
            owner_jid=Jid.from_raw(str(data.get("owner"))) if data.get("owner") else None,
            members=members,
            is_muted=False,
        )

    async def get_message_context(
        self,
        message_id: str,
        before: int = 5,
        after: int = 5,
    ) -> tuple[list[Message], Message | None]:
        await self._ensure_connected()
        js_code = f"""
        (async () => {{
            return new Promise((resolve, reject) => {{
                const req = window.indexedDB.open("model-storage");
                req.onsuccess = (e) => {{
                    const db = e.target.result;
                    const tx = db.transaction("message", "readonly");
                    const store = tx.objectStore("message");
                    const targetReq = store.get("{message_id}");

                    targetReq.onsuccess = () => {{
                        const target = targetReq.result;
                        if (!target) {{
                            db.close();
                            resolve({{ target: null, context: [] }});
                            return;
                        }}

                        const cursorReq = store.openCursor();
                        const allChatMsgs = [];
                        const targetChat = target.from;

                        cursorReq.onsuccess = (ev) => {{
                            const cur = ev.target.result;
                            if (cur) {{
                                const m = cur.value;
                                if (m.from === targetChat || m.to === targetChat) {{
                                    allChatMsgs.push({{
                                        id: m.id,
                                        t: m.t || 0,
                                        from: typeof m.from === 'object' ? (m.from._serialized || m.from.user) : m.from,
                                        to: typeof m.to === 'object' ? (m.to._serialized || m.to.user) : m.to,
                                        author: typeof m.author === 'object' ? (m.author._serialized || m.author.user) : m.author,
                                        body: m.body || m.caption || null,
                                        type: m.type || "chat",
                                        fromMe: String(m.id || "").startsWith("true_")
                                    }});
                                }}
                                cur.continue();
                            }} else {{
                                allChatMsgs.sort((a, b) => a.t - b.t);
                                const idx = allChatMsgs.findIndex(x => x.id === "{message_id}");
                                if (idx === -1) {{
                                    db.close();
                                    resolve({{ target, context: [] }});
                                    return;
                                }}
                                const start = Math.max(0, idx - {before});
                                const end = Math.min(allChatMsgs.length, idx + {after} + 1);
                                db.close();
                                resolve({{ target, context: allChatMsgs.slice(start, end) }});
                            }}
                        }};
                        cursorReq.onerror = () => {{ db.close(); reject(cursorReq.error); }};
                    }};
                    targetReq.onerror = () => {{ db.close(); reject(targetReq.error); }};
                }};
                req.onerror = () => reject(req.error);
            }});
        }})()
        """
        data = await self.cdp.evaluate(js_code)
        if not data or not data.get("target"):
            return [], None

        raw_target = data["target"]
        target_jid_str = raw_target.get("from") or ""
        c_id = _jid_to_chat_id(str(target_jid_str))
        target_msg = Message(
            message_id=_extract_msg_id(raw_target.get("id")),
            chat_id=c_id,
            sender_jid=Jid.from_raw(str(raw_target.get("author") or target_jid_str)),
            timestamp=raw_target.get("t", 0),
            body=raw_target.get("body"),
            kind=_map_message_kind(raw_target.get("type")),
            is_outgoing=str(raw_target.get("id", "")).startswith("true_"),
            quoted_message_id=_extract_quoted_msg_id(raw_target.get("quotedMsgId")),
        )

        context_msgs: list[Message] = []
        for rm in data.get("context", []):
            sender = rm.get("author") or rm.get("from") or ""
            context_msgs.append(
                Message(
                    message_id=_extract_msg_id(rm.get("id")),
                    chat_id=c_id,
                    sender_jid=Jid.from_raw(str(sender)),
                    timestamp=rm.get("t", 0),
                    body=rm.get("body"),
                    kind=_map_message_kind(rm.get("type")),
                    is_outgoing=rm.get("fromMe", False),
                    quoted_message_id=_extract_quoted_msg_id(rm.get("quotedMsgId")),
                )
            )

        return context_msgs, target_msg
