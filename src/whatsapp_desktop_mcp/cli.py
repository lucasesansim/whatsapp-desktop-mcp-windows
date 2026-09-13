"""Console-script entry point for ``whatsapp-desktop-mcp`` on Windows."""

from __future__ import annotations

import argparse
import os
import sys

from whatsapp_desktop_mcp import __version__


def _add_server_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--read-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Disable every send tool; tools/list returns read tools + doctor only. "
            "Default is on (read-only mode). Pass --no-read-only to enable sends."
        ),
    )
    parser.add_argument(
        "--audit-log-max-bytes",
        type=int,
        default=10 * 1024 * 1024,
        help="Audit log rotation threshold in bytes (default 10 MB).",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="whatsapp-desktop-mcp",
        description="MCP stdio server for the Windows WhatsApp Desktop app.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"whatsapp-desktop-mcp {__version__}",
    )
    _add_server_args(parser)

    subparsers = parser.add_subparsers(dest="cmd")
    dev_parser = subparsers.add_parser(
        "dev",
        help="developer utility subcommands (one-shot CLI; NOT the MCP server)",
    )
    dev_subparsers = dev_parser.add_subparsers(dest="dev_cmd")
    dev_subparsers.add_parser(
        "reset-rate-limit",
        help="clear rate-limit database after confirmation",
    )

    args = parser.parse_args(argv)

    if args.cmd == "dev" and args.dev_cmd == "reset-rate-limit":
        from whatsapp_desktop_mcp.dev.reset_rate_limit import run as dev_reset

        return dev_reset()

    from whatsapp_desktop_mcp import server

    server.set_read_only_mode(args.read_only)
    os.environ["WHATSAPP_DESKTOP_MCP_AUDIT_LOG_MAX_BYTES"] = str(args.audit_log_max_bytes)

    from whatsapp_desktop_mcp.server import run

    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
