"""Live integration tests against running WhatsApp Desktop on Windows."""

from __future__ import annotations

import os

import pytest

from whatsapp_desktop_mcp.tools.doctor import doctor
from whatsapp_desktop_mcp.tools.list_chats import list_chats
from whatsapp_desktop_mcp.tools.read_chat import read_chat
from whatsapp_desktop_mcp.tools.search_contacts import search_contacts

# Skip unless RUN_LIVE=1 or running manually
RUN_LIVE = os.environ.get("RUN_LIVE", "1") == "1"


@pytest.mark.skipif(not RUN_LIVE, reason="Live integration test requires running WhatsApp Desktop")
@pytest.mark.asyncio
async def test_live_doctor() -> None:
    report = await doctor()
    assert report["whatsapp_running"] is True
    assert report["cdp_connected"] is True
    assert report["session_authenticated"] is True
    assert report["can_read"] is True


@pytest.mark.skipif(not RUN_LIVE, reason="Live integration test requires running WhatsApp Desktop")
@pytest.mark.asyncio
async def test_live_list_chats() -> None:
    res = await list_chats(limit=5)
    assert res["count"] > 0
    assert len(res["chats"]) > 0
    first_chat = res["chats"][0]
    assert "chat_id" in first_chat
    assert "display_name" in first_chat
    assert "kind" in first_chat


@pytest.mark.skipif(not RUN_LIVE, reason="Live integration test requires running WhatsApp Desktop")
@pytest.mark.asyncio
async def test_live_read_chat() -> None:
    chats_res = await list_chats(limit=3)
    target_chat = chats_res["chats"][0]
    cid = target_chat["chat_id"]

    res = await read_chat(chat_id=cid, limit=5)
    assert res["chat_id"] == cid
    assert "messages" in res
    assert "coverage" in res


@pytest.mark.skipif(not RUN_LIVE, reason="Live integration test requires running WhatsApp Desktop")
@pytest.mark.asyncio
async def test_live_search_contacts() -> None:
    res = await search_contacts(query="a", limit=5)
    assert res["count"] > 0
    assert len(res["contacts"]) > 0
