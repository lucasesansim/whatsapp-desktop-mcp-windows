"""``whatsapp-desktop-mcp dev reset-rate-limit`` — clear the rate-limit DB on Windows."""

from __future__ import annotations

import sys

from whatsapp_desktop_mcp.paths import get_rate_limit_db_path


def run() -> int:
    """Prompt for confirmation; on yes, delete the rate-limit DB."""
    db_path = get_rate_limit_db_path()

    if not db_path.exists():
        print(f"No rate-limit DB at {db_path}; nothing to reset.")
        return 0

    if not sys.stdin.isatty():
        print(
            "Refusing to reset rate-limit DB from a non-tty (no interactive "
            "confirmation possible). Run from an interactive shell.",
            file=sys.stderr,
        )
        return 1

    print(
        f"This will erase all rate-limit history at {db_path}. Continue? [y/N] ",
        end="",
        flush=True,
    )
    answer = sys.stdin.readline().strip().lower()
    if answer != "y":
        print("Aborted.")
        return 1

    try:
        db_path.unlink(missing_ok=True)
    except (PermissionError, OSError) as ex:
        print(f"Failed to remove {db_path}: {ex}", file=sys.stderr)
        return 1

    print(f"Removed {db_path}.")
    return 0
