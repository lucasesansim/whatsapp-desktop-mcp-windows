"""Keep synthetic tests away from user state and the live WhatsApp session."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_DATA_DIR", str(tmp_path / "mcp"))
    from whatsapp_desktop_mcp import server

    monkeypatch.setattr(server, "read_only_mode", True)
    if os.environ.get("RUN_LIVE") != "1":
        import urllib.request

        from whatsapp_desktop_mcp.windows.cdp_client import CDPClient

        def no_network(*args, **kwargs):
            raise AssertionError("Synthetic tests must not contact a WhatsApp session.")

        monkeypatch.setattr(urllib.request, "urlopen", no_network)
        monkeypatch.setattr(CDPClient, "connect", AsyncMock(side_effect=no_network))
