"""Require an actual MCP client confirmation for every outbound operation."""

from __future__ import annotations

from typing import Any

from mcp.server.elicitation import AcceptedElicitation

from whatsapp_desktop_mcp.models.send import ConfirmationSchema


async def confirmed(ctx: Any, prompt: str) -> bool:
    if ctx is None:
        raise ValueError("Sending requires an MCP client with interactive confirmation.")
    result = await ctx.elicit(message=prompt, schema=ConfirmationSchema)
    return isinstance(result, AcceptedElicitation) and result.data.confirm is True
