"""Unit tests for sliding-window rate limiter."""

from __future__ import annotations

import pytest

from whatsapp_desktop_mcp.exceptions import RateLimitExceeded
from whatsapp_desktop_mcp.sender import rate_limit


@pytest.fixture(autouse=True)
def clean_rate_limit_db(tmp_path, monkeypatch) -> None:
    test_db = tmp_path / "test_rate_limit.db"
    monkeypatch.setattr(rate_limit, "get_rate_limit_db_path", lambda: test_db)
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_RATE_PER_MIN", "3")
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_RATE_PER_DAY", "5")


@pytest.mark.asyncio
async def test_rate_limit_allow_and_exhaust() -> None:
    rem_min, rem_day = await rate_limit.check_and_reserve()
    assert rem_min == 3
    assert rem_day == 5

    # Record 3 sends
    await rate_limit.record_outcome(101, "sha_1", "sent")
    await rate_limit.record_outcome(101, "sha_2", "sent")
    await rate_limit.record_outcome(101, "sha_3", "sent")

    # 4th send within the minute must raise RateLimitExceeded
    with pytest.raises(RateLimitExceeded) as exc_info:
        await rate_limit.check_and_reserve()
    assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancelled_does_not_consume_rate_limit() -> None:
    await rate_limit.record_outcome(101, "sha_cancelled", "cancelled")
    await rate_limit.record_outcome(101, "sha_error", "error")

    # Cancelled and error sends should NOT count against budget
    rem_min, rem_day = await rate_limit.check_and_reserve()
    assert rem_min == 3
    assert rem_day == 5


def test_reset_rate_limit() -> None:
    rate_limit._record_outcome_sync(101, "sha_1", "sent")
    rate_limit.reset_rate_limit_sync()

    rem_min, rem_day = rate_limit._check_and_reserve_sync()
    assert rem_min == 3
    assert rem_day == 5
