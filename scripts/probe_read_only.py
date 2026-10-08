"""One-shot read-only probe. Prints aggregate counts and timings only."""

import argparse
import asyncio
import json
import logging
import statistics
import time
from pathlib import Path

from whatsapp_desktop_mcp.windows.cdp_client import CDPClient
from whatsapp_desktop_mcp.windows.idb_reader import IndexedDBReader

logging.disable(logging.CRITICAL)


async def main(report_path: Path):
    client = CDPClient()
    reader = IndexedDBReader(client)
    result = {"mode": "read_only", "messages_sent": 0}
    stage = "connect"
    try:
        async with asyncio.timeout(25):
            started = time.perf_counter()
            await client.connect()
            result["connect_ms"] = round((time.perf_counter() - started) * 1000, 1)
            stage = "list_chats"
            times = []
            chats = []
            for _ in range(3):
                started = time.perf_counter()
                chats = await reader.list_chats(limit=5)
                times.append(round((time.perf_counter() - started) * 1000, 1))
            result["chat_sample_count"] = len(chats)
            result["list_chats_ms"] = times
            result["list_chats_median_ms"] = statistics.median(times)
            if chats:
                stage = "read_chat"
                times = []
                messages = []
                for _ in range(3):
                    started = time.perf_counter()
                    messages, _ = await reader.read_chat(chats[0].chat_id, limit=5)
                    times.append(round((time.perf_counter() - started) * 1000, 1))
                result["message_sample_count"] = len(messages)
                result["messages_with_text"] = sum(bool(m.body) for m in messages)
                result["read_chat_ms"] = times
                result["read_chat_median_ms"] = statistics.median(times)
            result["status"] = "ok"
    except Exception as error:
        result.update(status="error", stage=stage, error_type=type(error).__name__)
    finally:
        await client.close()
    report = report_path
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))  # noqa: T201 - standalone report, not MCP stdio
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(main(arguments.report)))
