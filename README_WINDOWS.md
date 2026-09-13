# WhatsApp Desktop MCP — Windows Edition

A Model Context Protocol (MCP) server that provides read and send access to the official **WhatsApp Desktop** application on Windows.

Controls and queries the official WhatsApp Desktop app (WinUI 3 + Edge WebView2) already installed and authenticated on the user's machine, with **zero modifications** to WhatsApp files, **no reverse-engineered WhatsApp Web sessions**, **no Baileys**, **no WhatsMeow**, and **no third-party WhatsApp APIs**.

---

## Architecture Overview

```
HARNESS (Claude Desktop / Antigravity / Any MCP Client)
  │ (stdio JSON-RPC 2.0 frames)
  ▼
WhatsApp Desktop MCP (Windows)
  │ (CDP WebSocket on 127.0.0.1:9224)
  ▼
Edge WebView2 Runtime (msedgewebview2.exe)
  │ (Read-only IndexedDB transactions & UI automation)
  ▼
Official WhatsApp Desktop (WhatsApp.Root.exe)
  │ (End-to-End Encrypted Signal Protocol via phone multi-device)
  ▼
User's Authenticated WhatsApp Account
```

### Key Technical Achievements

1. **Official WhatsApp Desktop Integration:** Targets the official Microsoft Store UWP/MSIX package (`5319275A.WhatsAppDesktop_...`).
2. **Encrypted Storage Bypass via Live Process:** While local SQLite databases on Windows (`contacts.db`, `genericStorage.db`) are encrypted with SQLCipher/Meta proprietary keys, the live Edge WebView2 runtime hosts an unencrypted, synchronous `model-storage` IndexedDB database holding the full decrypted sync cache (chats, messages, contacts, groups).
3. **Sub-100ms Read Performance:** Reads data via direct, readonly IndexedDB transactions executed inside the origin `web.whatsapp.com` through Chrome DevTools Protocol (CDP).
4. **Desktop-Independent Headless Reads:** CDP evaluation does not require the WhatsApp window to be in the foreground or on the active desktop station.
5. **Strict Security & Privacy:**
   - Starts in `--read-only` mode by default (gating all send tools).
   - Sending requires explicit human confirmation via MCP elicitation prompt.
   - Sliding-window rate limiter (5 sends/minute, 30 sends/day).
   - Rotating JSONL audit log with SHA-256 message body hashes — **never writes plaintext message bodies to disk**.
   - Cross-chat quote detection heuristics preventing accidental information leakage across conversations.
   - Stdout purity: 100% of logging directed to stderr, preserving stdio for JSON-RPC 2.0 frames.

---

## Prerequisites

1. **Windows 10 / 11** (64-bit).
2. **WhatsApp Desktop for Windows** installed from the [Microsoft Store](ms-windows-store://pdp/?productid=9NKSQGP7F2NH) and logged in with your account.
3. **Python 3.12+** (managed via `uv` or system Python).
4. **WebView2 Remote Debugging Port Enabled:**
   Set the user environment variable:
   ```powershell
   [Environment]::SetEnvironmentVariable("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--remote-debugging-port=9224", "User")
   ```
   *Note: After setting this variable, restart WhatsApp Desktop completely (`Get-Process WhatsApp.Root -ErrorAction SilentlyContinue | Stop-Process -Force` then launch `start whatsapp:`).*

---

## Quick Start & Installation

### Using `uv` (Recommended)

```powershell
# Clone or navigate to the repository
cd c:\Users\crist\Downloads\_node\whatsapp-desktop-mcp-windows

# Install dependencies and build virtual environment
uv sync

# Run diagnostics
uv run whatsapp-desktop-mcp --help
```

---

## Tools Reference

The server exposes the exact toolset and contract as the macOS reference implementation:

### 1. Diagnostic Preflight
- **`doctor`**: Verifies WhatsApp Desktop installation, process execution, Edge WebView2 CDP endpoint connectivity on port 9224, and IndexedDB storage readiness.

### 2. Read Operations (Read-Only Hint)
- **`list_chats(limit=200)`**: Lists conversations (1:1 and groups) ordered by last activity timestamp, with unread count and coverage window metadata.
- **`read_chat(chat_id, limit=50, before=None, after=None, cursor=None)`**: Reads messages newest-first with cursor-based pagination and a 60,000-character safety ceiling.
- **`extract_recent(chat_id, hours=24)`**: Extracts all messages within the last N hours with human-readable coverage summary (`asked Xh, have Yh`).
- **`search_messages(query, chat_id=None, sender_jid=None, before=None, after=None, limit=50, cursor=None)`**: Substring search across message bodies with optional filters and cursor pagination.
- **`search_contacts(query, limit=20)`**: Searches contacts and chat partners by name or phone number fragment.
- **`get_chat_metadata(chat_id)`**: Retrieves group subject, description, creation timestamp, admin status, and member roster.
- **`get_message_context(message_id, before=5, after=5)`**: Returns contextual messages before and after a specific message ID.

### 3. Send Operations (Requires `--no-read-only`)
- **`send_message(chat_id, body)`**: Sends a WhatsApp text message to a resolved `chat_id`.
  - Automatically focuses the conversation in WhatsApp Desktop (no need to click manually).
  - Prompts the user with full verbatim text and recipient details for human approval.
  - Enforces sliding window rate limits (5/min, 30/day).
  - Verifies outgoing delivery in IndexedDB.
  - Records cryptographic audit trail.
- **`send_file(chat_id, file_path, caption="")`**: Sends a file attachment (PDF reports, images, documents, spreadsheets) with optional caption to a resolved `chat_id`.
  - Opens the conversation automatically in the background.
  - Loads the file via native WebView2 file input and attaches it in the media preview stage.
  - Types the optional caption and triggers send.
  - Records SHA-256 file hash and caption hash in the audit log (never storing binary or plaintext files).
  - Verifies outgoing media in IndexedDB.

---

## Configuration in Claude Desktop / Antigravity

Add to your `claude_desktop_config.json` (or Antigravity MCP settings):

### Read-Only Mode (Default & Safe)

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:\\Users\\crist\\Downloads\\_node\\whatsapp-desktop-mcp-windows",
        "whatsapp-desktop-mcp",
        "--read-only"
      ]
    }
  }
}
```

### Full Mode (With Send Capability)

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:\\Users\\crist\\Downloads\\_node\\whatsapp-desktop-mcp-windows",
        "whatsapp-desktop-mcp",
        "--no-read-only"
      ]
    }
  }
}
```

---

## Developer Commands

```powershell
# Run the test suite
uv run pytest

# Reset rate-limit database
uv run whatsapp-desktop-mcp dev reset-rate-limit
```

---

## License

MIT License. See LICENSE for details.
