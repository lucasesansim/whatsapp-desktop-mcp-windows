"""Asynchronous Chrome DevTools Protocol (CDP) WebSocket client."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

from whatsapp_desktop_mcp.exceptions import CDPConnectionError, TargetNotFoundError
from whatsapp_desktop_mcp.windows.discovery import (
    DEFAULT_CDP_PORT,
    get_whatsapp_page_target,
)

logger = logging.getLogger(__name__)


class CDPClient:
    """Async WebSocket client connecting to the WebView2 Chrome DevTools Protocol."""

    def __init__(self, port: int = DEFAULT_CDP_PORT) -> None:
        self.port = port
        self.ws: Any = None
        self._msg_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._listener_task: asyncio.Task[None] | None = None
        self._lock: asyncio.Lock | None = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _is_open(self) -> bool:
        if not self.ws:
            return False
        try:
            current_loop = asyncio.get_running_loop()
            ws_loop = getattr(self.ws, "loop", getattr(self.ws, "_loop", None))
            if ws_loop is not None and (ws_loop != current_loop or ws_loop.is_closed()):
                return False
        except RuntimeError:
            pass
        if hasattr(self.ws, "state"):
            from websockets.protocol import State

            return self.ws.state == State.OPEN
        if hasattr(self.ws, "closed"):
            return not self.ws.closed
        return getattr(self.ws, "close_code", None) is None

    async def connect(self) -> None:
        """Connect to the WhatsApp page target WebSocket."""
        async with self.lock:
            if self._is_open():
                return

            target = get_whatsapp_page_target(self.port)
            if not target:
                raise TargetNotFoundError(
                    f"No WhatsApp page target found on CDP port {self.port}. "
                    "Ensure WhatsApp Desktop is running with remote debugging enabled."
                )

            ws_url = target.get("webSocketDebuggerUrl")
            if not ws_url:
                raise CDPConnectionError(f"No webSocketDebuggerUrl on target: {target}")

            try:
                self.ws = await websockets.connect(
                    ws_url,
                    max_size=50 * 1024 * 1024,  # 50MB max frame
                    ping_interval=20,
                    ping_timeout=20,
                )
                self._listener_task = asyncio.create_task(self._listen_loop())
                logger.info("Connected to WhatsApp CDP at %s", ws_url)
            except Exception as exc:
                raise CDPConnectionError(
                    f"Failed to connect to CDP WebSocket {ws_url}: {exc}"
                ) from exc

    async def _listen_loop(self) -> None:
        """Background loop receiving incoming WebSocket frames and resolving pending futures."""
        try:
            async for raw in self.ws:
                try:
                    data = json.loads(raw)
                    msg_id = data.get("id")
                    if msg_id and msg_id in self._pending:
                        fut = self._pending.pop(msg_id)
                        if "error" in data:
                            fut.set_exception(RuntimeError(data["error"]))
                        else:
                            fut.set_result(data.get("result", {}))
                except Exception as parse_err:
                    logger.warning("Error processing CDP frame: %s", parse_err)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("CDP listen loop closed: %s", exc)
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(CDPConnectionError(f"CDP connection lost: {exc}"))
            self._pending.clear()

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a CDP command and wait for the result."""
        if not self._is_open():
            await self.connect()

        async with self.lock:
            msg_id = self._msg_id
            self._msg_id += 1

        payload = {"id": msg_id, "method": method, "params": params or {}}
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[msg_id] = fut

        try:
            await self.ws.send(json.dumps(payload))
            return await asyncio.wait_for(fut, timeout=15.0)
        except Exception as exc:
            self._pending.pop(msg_id, None)
            raise exc

    async def evaluate(
        self,
        expression: str,
        await_promise: bool = True,
        return_by_value: bool = True,
    ) -> Any:
        """Evaluate a JavaScript expression in the page execution context."""
        res = await self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": return_by_value,
            },
        )
        if "exceptionDetails" in res:
            exc = res["exceptionDetails"]
            text = exc.get("text", "")
            val = exc.get("exception", {}).get("description", "")
            raise RuntimeError(f"JavaScript evaluation error: {text} - {val}")

        result_obj = res.get("result", {})
        return result_obj.get("value")

    async def close(self) -> None:
        """Close the WebSocket connection cleanly."""
        if self._listener_task:
            self._listener_task.cancel()
        if self.ws:
            await self.ws.close()
            self.ws = None
