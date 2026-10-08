"""FastMCP stdio server for WhatsApp Desktop on Windows."""

from __future__ import annotations

import logging
import sys

# CRITICAL: configure logging to stderr BEFORE any third-party import.
# stdout is exclusively reserved for JSON-RPC 2.0 frames.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from mcp.server.fastmcp import FastMCP  # noqa: E402

from whatsapp_desktop_mcp.windows.cdp_client import CDPClient  # noqa: E402
from whatsapp_desktop_mcp.windows.idb_reader import IndexedDBReader  # noqa: E402
from whatsapp_desktop_mcp.windows.sender import WindowsCDPTransport  # noqa: E402

mcp: FastMCP = FastMCP("whatsapp-desktop-mcp")

# Module-level read-only mode flag set by CLI before tool imports
read_only_mode: bool = True

# Shared Windows integration singletons

cdp_client = CDPClient()
reader = IndexedDBReader(cdp_client)
transport = WindowsCDPTransport(cdp_client)

# Register read tools
from whatsapp_desktop_mcp.tools import doctor as _doctor  # noqa: E402, F401
from whatsapp_desktop_mcp.tools import extract_recent as _extract_recent  # noqa: E402, F401
from whatsapp_desktop_mcp.tools import get_chat_metadata as _get_chat_metadata  # noqa: E402, F401
from whatsapp_desktop_mcp.tools import (  # noqa: E402
    get_message_context as _get_message_context,  # noqa: F401
)
from whatsapp_desktop_mcp.tools import list_chats as _list_chats  # noqa: E402, F401
from whatsapp_desktop_mcp.tools import read_chat as _read_chat  # noqa: E402, F401
from whatsapp_desktop_mcp.tools import search_contacts as _search_contacts  # noqa: E402, F401
from whatsapp_desktop_mcp.tools import search_messages as _search_messages  # noqa: E402, F401

# Send tools registered ONLY when read_only_mode is False
if not read_only_mode:
    from whatsapp_desktop_mcp.tools import send_file as _send_file  # noqa: E402, F401
    from whatsapp_desktop_mcp.tools import send_message as _send_message  # noqa: E402, F401


def set_read_only_mode(enabled: bool) -> None:
    """Set read-only mode and register send tools if disabled."""
    global read_only_mode
    read_only_mode = enabled
    if not read_only_mode:
        from whatsapp_desktop_mcp.tools import send_file as _send_file  # noqa: F401
        from whatsapp_desktop_mcp.tools import send_message as _send_message  # noqa: F401


def run() -> None:
    """Start the stdio JSON-RPC loop."""
    if not read_only_mode:
        from whatsapp_desktop_mcp.tools import send_file as _send_file  # noqa: F401
        from whatsapp_desktop_mcp.tools import send_message as _send_message  # noqa: F401
    mcp.run()
