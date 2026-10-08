"""The doctor MCP tool — preflight diagnostic for WhatsApp Desktop Windows."""

from __future__ import annotations

import logging
from typing import Any

from mcp.types import ToolAnnotations

from whatsapp_desktop_mcp.models.doctor import ComponentStatus, DoctorReport
from whatsapp_desktop_mcp.server import mcp, read_only_mode
from whatsapp_desktop_mcp.windows.discovery import (
    DEFAULT_CDP_PORT,
    get_cdp_endpoint,
    get_whatsapp_page_target,
    is_whatsapp_installed,
    is_whatsapp_process_running,
)

logger = logging.getLogger(__name__)


@mcp.tool(
    name="doctor",
    title="WhatsApp Desktop Diagnostic Doctor",
    description=(
        "Performs a comprehensive preflight health check of the local WhatsApp Desktop "
        "application on Windows. Verifies installation, process status, Edge WebView2 "
        "Chrome DevTools Protocol (CDP) connectivity, active session, and database readiness."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
    meta={"anthropic/maxResultSizeChars": 60_000},
)
async def doctor() -> dict[str, Any]:
    """Run diagnostics and return a structured DoctorReport."""
    components: list[ComponentStatus] = []

    # 1. Check Installation
    installed, version_str, install_path = is_whatsapp_installed()
    if installed:
        components.append(
            ComponentStatus(
                name="whatsapp_installation",
                state="ok",
                details=f"Installed version {version_str or 'unknown'} at {install_path}",
            )
        )
    else:
        components.append(
            ComponentStatus(
                name="whatsapp_installation",
                state="error",
                details="WhatsApp Desktop is not installed from the Microsoft Store.",
                remediation="Install WhatsApp from Microsoft Store: ms-windows-store://pdp/?productid=9NKSQGP7F2NH",
            )
        )

    # 2. Check Running Process
    running = is_whatsapp_process_running()
    if running:
        components.append(
            ComponentStatus(
                name="whatsapp_process",
                state="ok",
                details="WhatsApp.Root.exe process is active.",
            )
        )
    else:
        components.append(
            ComponentStatus(
                name="whatsapp_process",
                state="error",
                details="WhatsApp.Root.exe is not running.",
                remediation="Start WhatsApp Desktop from the Start Menu or run 'start whatsapp:'.",
            )
        )

    # 3. Check CDP Remote Debugging
    cdp_endpoint = get_cdp_endpoint(DEFAULT_CDP_PORT)
    cdp_ok = cdp_endpoint is not None
    if cdp_ok:
        components.append(
            ComponentStatus(
                name="cdp_remote_debugging",
                state="ok",
                details=f"CDP active and listening on port {DEFAULT_CDP_PORT}.",
            )
        )
    else:
        components.append(
            ComponentStatus(
                name="cdp_remote_debugging",
                state="warning" if running else "unavailable",
                details=f"No CDP endpoint detected on port {DEFAULT_CDP_PORT}.",
                remediation=(
                    "Review README's app-scoped debugging procedure. "
                    "Do not set global WebView2 variables or change Windows permissions."
                ),
            )
        )

    # 4. Check Page Target & Authentication
    target = get_whatsapp_page_target(DEFAULT_CDP_PORT) if cdp_ok else None
    target_title = target.get("title") if target else None
    authenticated = False
    stores: dict[str, int] = {}
    can_read = False

    if target:
        components.append(
            ComponentStatus(
                name="whatsapp_web_target",
                state="ok",
                details=f"Located page target: '{target_title}'",
            )
        )
        # Test IndexedDB read
        try:
            from whatsapp_desktop_mcp.server import reader

            chats = await reader.list_chats(limit=5)
            can_read = True
            authenticated = len(chats) > 0
            stores["chats_sample"] = len(chats)
            components.append(
                ComponentStatus(
                    name="indexeddb_reader",
                    state="ok",
                    details=f"Successfully read active chat history ({len(chats)} sample chats retrieved).",
                )
            )
        except Exception as exc:
            logger.warning("Doctor reading probe failed: %s", exc)
            components.append(
                ComponentStatus(
                    name="indexeddb_reader",
                    state="error",
                    details=f"Failed to read IndexedDB: {exc}",
                )
            )
    else:
        components.append(
            ComponentStatus(
                name="whatsapp_web_target",
                state="unavailable",
                details="Target page for web.whatsapp.com was not found.",
            )
        )

    report = DoctorReport(
        whatsapp_installed=installed,
        whatsapp_running=running,
        whatsapp_package_version=version_str,
        whatsapp_exe_path=install_path,
        package_family_name="5319275A.WhatsAppDesktop_cv1g1gvanyjgm",
        cdp_connected=cdp_ok,
        cdp_port=DEFAULT_CDP_PORT,
        session_authenticated=authenticated,
        active_target_title=target_title,
        can_read=can_read,
        can_send=not read_only_mode and can_read,
        read_only_mode=read_only_mode,
        indexeddb_stores=stores,
        components=components,
    )
    return report.model_dump(mode="json")
