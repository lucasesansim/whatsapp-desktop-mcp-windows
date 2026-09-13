"""Allow running via python -m whatsapp_desktop_mcp."""

from __future__ import annotations

import sys

from whatsapp_desktop_mcp.cli import main

if __name__ == "__main__":
    sys.exit(main())
