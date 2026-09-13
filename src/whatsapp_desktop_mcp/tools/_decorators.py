"""@timeout(seconds=N) decorator — wraps an async tool body in asyncio.wait_for."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def timeout(seconds: float) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Wrap an async tool body in asyncio.wait_for(..., timeout=seconds)."""

    def deco(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(fn)
        async def inner(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=seconds)
            except TimeoutError as exc:
                raise ValueError(
                    f"Tool exceeded {seconds}s timeout. WhatsApp Desktop might be under load."
                ) from exc

        return inner

    return deco
