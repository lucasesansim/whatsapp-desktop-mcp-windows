"""Path resolver for WhatsApp Desktop and MCP state on Windows."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_FAMILY_NAME = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm"


def get_mcp_data_dir() -> Path:
    """Return the local data directory for the MCP server on Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    path = Path(local_app_data) / "whatsapp-desktop-mcp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_rate_limit_db_path() -> Path:
    """Return the path to the rate-limit SQLite database."""
    return get_mcp_data_dir() / "rate-limit.db"


def get_audit_log_path() -> Path:
    """Return the path to the JSONL audit log."""
    return get_mcp_data_dir() / "audit.log"


def get_whatsapp_package_data_dir() -> Path:
    """Return the WhatsApp AppData package folder in LocalAppData."""
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    return Path(local_app_data) / "Packages" / PACKAGE_FAMILY_NAME


def get_whatsapp_ebwebview_dir() -> Path:
    """Return the WebView2 user data folder for WhatsApp."""
    return get_whatsapp_package_data_dir() / "LocalCache" / "EBWebView"


def get_whatsapp_localstate_dir() -> Path:
    """Return the LocalState directory for WhatsApp."""
    return get_whatsapp_package_data_dir() / "LocalState"
