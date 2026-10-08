"""Reject misleading titles, lookalike origins and nonlocal debugging targets."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from whatsapp_desktop_mcp.exceptions import CDPConnectionError
from whatsapp_desktop_mcp.windows.cdp_client import CDPClient
from whatsapp_desktop_mcp.windows.discovery import validate_debug_target

ORIGINAL_CONNECT = CDPClient.connect


def target(**changes):
    value = {
        "type": "page", "title": "WhatsApp",
        "url": "https://web.whatsapp.com/",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9224/devtools/page/FAKE",
    }
    value.update(changes)
    return value


@pytest.mark.parametrize("changes", [
    {"url": "https://web.whatsapp.com.evil.example/"},
    {"url": "https://evil.example/web.whatsapp.com"},
    {"url": "https://evil.example/", "title": "WhatsApp"},
    {"url": "http://web.whatsapp.com/"},
    {"url": "https://user@web.whatsapp.com/"},
    {"url": "https://web.whatsapp.com:444/"},
    {"type": "service_worker"},
    {"webSocketDebuggerUrl": "ws://192.0.2.1:9224/devtools/page/FAKE"},
    {"webSocketDebuggerUrl": "ws://127.0.0.1:9225/devtools/page/FAKE"},
    {"webSocketDebuggerUrl": "ws://127.0.0.1:9224/devtools/page/FAKE?token=secret"},
    {"webSocketDebuggerUrl": "ws://user:pass@127.0.0.1:9224/devtools/page/FAKE"},
    {"webSocketDebuggerUrl": "ws://127.0.0.1:9224/devtools/browser/FAKE"},
    {"webSocketDebuggerUrl": "ws://127.0.0.1:bad/devtools/page/FAKE"},
    {"webSocketDebuggerUrl": None},
])
def test_untrusted_debug_target_rejected(changes):
    assert validate_debug_target(target(**changes), 9224) is False


def test_exact_local_whatsapp_target_accepted():
    assert validate_debug_target(target(), 9224) is True


@pytest.mark.asyncio
async def test_client_revalidates_target_before_connecting(monkeypatch):
    from whatsapp_desktop_mcp.windows import cdp_client

    monkeypatch.setattr(CDPClient, "connect", ORIGINAL_CONNECT)
    connect = AsyncMock()
    monkeypatch.setattr(cdp_client, "get_whatsapp_page_target", lambda port: target(url="https://evil.example/"))
    monkeypatch.setattr(cdp_client.websockets, "connect", connect)
    with pytest.raises(CDPConnectionError, match="Untrusted"):
        await CDPClient().connect()
    connect.assert_not_awaited()
