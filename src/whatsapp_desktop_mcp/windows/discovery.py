"""Discovery module for WhatsApp Desktop Windows and WebView2 CDP endpoint."""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from whatsapp_desktop_mcp.paths import get_whatsapp_package_data_dir

logger = logging.getLogger(__name__)

DEFAULT_CDP_PORT = int(os.environ.get("WHATSAPP_CDP_PORT", "9224"))


def is_whatsapp_installed() -> tuple[bool, str | None, str | None]:
    """Check if WhatsApp Desktop is installed on Windows.

    Returns (is_installed, version_str, install_path).
    """
    package_dir = get_whatsapp_package_data_dir()
    if not package_dir.exists():
        # Check standard WindowsApps
        win_apps = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "WindowsApps"
        matches = list(win_apps.glob("5319275A.WhatsAppDesktop_*")) if win_apps.exists() else []
        if not matches:
            return False, None, None

    # Check WindowsApps directory
    win_apps = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "WindowsApps"
    if win_apps.exists():
        matches = sorted(win_apps.glob("5319275A.WhatsAppDesktop_*_x64__*"))
        if matches:
            latest = matches[-1]
            # Parse version from folder name, e.g. 5319275A.WhatsAppDesktop_2.2635.100.0_x64__...
            parts = latest.name.split("_")
            ver = parts[1] if len(parts) > 1 else None
            exe = latest / "WhatsApp.Root.exe"
            return True, ver, str(exe) if exe.exists() else str(latest)

    return package_dir.exists(), None, str(package_dir)


def is_whatsapp_process_running() -> bool:
    """Check via tasklist if WhatsApp.Root.exe or msedgewebview2 is running."""
    try:
        import subprocess

        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq WhatsApp.Root.exe", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return "WhatsApp.Root.exe" in output
    except Exception as exc:
        logger.debug("tasklist check failed: %s", exc)
        return False


def get_cdp_endpoint(port: int = DEFAULT_CDP_PORT) -> str | None:
    """Return the HTTP URL of the CDP endpoint if responsive."""
    url = f"http://127.0.0.1:{port}/json/version"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                return f"http://127.0.0.1:{port}"
    except Exception:
        pass
    return None


def get_whatsapp_page_target(port: int = DEFAULT_CDP_PORT) -> dict[str, Any] | None:
    """Find the WhatsApp web page target from /json/list."""
    url = f"http://127.0.0.1:{port}/json/list"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for target in data:
                if isinstance(target, dict) and validate_debug_target(target, port):
                    return target
    except Exception as exc:
        logger.debug("Failed to get targets from %s: %s", url, exc)
    return None


def validate_debug_target(target: dict[str, Any], port: int) -> bool:
    """Accept only the exact WhatsApp origin and a same-port loopback debugger."""
    try:
        page = urlsplit(target.get("url", ""))
        debugger = urlsplit(target.get("webSocketDebuggerUrl", ""))
        return (
            target.get("type") == "page"
            and page.scheme == "https"
            and page.hostname == "web.whatsapp.com"
            and page.port in (None, 443)
            and page.username is None and page.password is None
            and debugger.scheme == "ws"
            and debugger.hostname == "127.0.0.1"
            and debugger.port == port
            and debugger.username is None and debugger.password is None
            and not debugger.query and not debugger.fragment
            and debugger.path.startswith("/devtools/page/")
            and len(debugger.path) > len("/devtools/page/")
        )
    except (AttributeError, TypeError, ValueError):
        return False
