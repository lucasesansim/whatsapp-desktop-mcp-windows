"""Doctor report models for WhatsApp Desktop Windows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whatsapp_desktop_mcp.models.coverage import Coverage

StatusState = Literal["ok", "warning", "error", "unavailable"]


class ComponentStatus(BaseModel):
    name: str
    state: StatusState
    details: str = ""
    remediation: str | None = None


class DoctorReport(BaseModel):
    """Structured report returned by the doctor tool."""

    whatsapp_installed: bool
    whatsapp_running: bool
    whatsapp_package_version: str | None = None
    whatsapp_exe_path: str | None = None
    package_family_name: str | None = None
    cdp_connected: bool = False
    cdp_port: int = 9224
    session_authenticated: bool = False
    active_target_title: str | None = None
    can_read: bool = False
    can_send: bool = False
    read_only_mode: bool = True
    indexeddb_stores: dict[str, int] = Field(default_factory=dict)
    components: list[ComponentStatus] = Field(default_factory=list)
    coverage_summary: Coverage | None = None

    @property
    def all_ok(self) -> bool:
        return (
            self.whatsapp_installed
            and self.whatsapp_running
            and self.cdp_connected
            and self.can_read
        )
