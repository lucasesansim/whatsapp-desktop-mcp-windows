"""Windows integration components."""

from whatsapp_desktop_mcp.windows.cdp_client import CDPClient
from whatsapp_desktop_mcp.windows.discovery import (
    get_cdp_endpoint,
    get_whatsapp_page_target,
    is_whatsapp_installed,
    is_whatsapp_process_running,
)
from whatsapp_desktop_mcp.windows.idb_reader import IndexedDBReader
from whatsapp_desktop_mcp.windows.sender import WindowsCDPTransport

__all__ = [
    "CDPClient",
    "IndexedDBReader",
    "WindowsCDPTransport",
    "get_cdp_endpoint",
    "get_whatsapp_page_target",
    "is_whatsapp_installed",
    "is_whatsapp_process_running",
]
