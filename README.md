# WhatsApp Desktop MCP — Windows Edition 🚀

[![Platform: Windows 10/11](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?logo=windows&logoColor=white)](https://microsoft.com)
[![Protocol: Model Context Protocol](https://img.shields.io/badge/MCP-Standard%20v1.27-blueviolet)](https://modelcontextprotocol.io)
[![Runtime: Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Automation: Edge WebView2 CDP](https://img.shields.io/badge/Driver-Edge%20WebView2%20CDP-008272?logo=microsoftedge&logoColor=white)](https://developer.microsoft.com/microsoft-edge/webview2/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-grade **Model Context Protocol (MCP)** server providing seamless read and send automation for the official **WhatsApp Desktop** application on Windows.

Controls and queries the official WhatsApp Desktop app (WinUI 3 + Edge WebView2) installed and authenticated on your machine with **zero modifications to WhatsApp code**, **zero reverse-engineered browser sessions**, **no Baileys**, **no WhatsMeow**, and **no third-party cloud APIs**.

---

## 🌟 Live Documentation & Interactive Page

Visit our interactive project documentation page:  
👉 **[https://Cristinacarolsouza.github.io/whatsapp-desktop-mcp-windows/](https://Cristinacarolsouza.github.io/whatsapp-desktop-mcp-windows/)**

---

## 🧠 Architectural Overview

```
MCP CLIENT (Antigravity / Claude Desktop / Cursor)
  │ (stdio JSON-RPC 2.0 frames)
  ▼
WhatsApp Desktop MCP (Windows)
  │ (CDP WebSocket connection on 127.0.0.1:9224)
  ▼
Edge WebView2 Runtime (msedgewebview2.exe)
  │ (Direct read-only IndexedDB transactions & UI input injection)
  ▼
Official WhatsApp Desktop (WhatsApp.Root.exe)
  │ (End-to-End Encrypted Signal Protocol via Multi-Device)
  ▼
Official WhatsApp Network
```

### Why This Architecture Wins
- **Official App Native Execution:** Runs within the user's authentic Windows desktop session.
- **Instant Decrypted Sync via `model-storage`:** Local SQLite databases on Windows are encrypted with proprietary keys, but the live WebView2 engine maintains an in-memory decrypted sync cache (`model-storage` IndexedDB) that answers queries in under 50ms.
- **Headless & Background Operation:** Operates without requiring the WhatsApp window to be in the foreground.
- **End-to-End Encryption Maintained:** All packets leave through WhatsApp's official binary client protocol.

---

## 💎 The Gold Standard: Attachment-First Workflow ("Anexo Primeiro")

When developing autonomous AI agents and automated pipelines, one behavioral habit is **paramount** for rock-solid reliability:

> ### 📌 Regra de Ouro do Fluxo de Envio: **Anexo Primeiro, Texto Depois**
> Ao entregar qualquer documento técnico, prancha arquitetônica, relatório PDF, imagem de alta resolução ou planilha acompanhada de explicação textual:
> 
> 1. **Envie o Anexo Primeiro (`send_file`)**: Carrega a mídia na conversa e utiliza o campo `caption` para a legenda imediata.
> 2. **Envie o Texto Complementar Depois (`send_message`)**: Caso haja comentários extensos ou instruções adicionais, envie-os em seguida.
> 
> **Por que esse hábito é essencial?**  
> - Evita *race conditions* na interface de composição do WhatsApp.
> - O anexo é processado e renderizado como âncora principal na conversa antes que mensagens complementares cheguem.
> - Previne que mensagens de texto quebrem a linha de raciocínio do cliente enquanto o documento ainda estivesse carregando.

---

## 🛠️ Complete Tools Reference

| Tool | Mode | Description |
|---|:---:|---|
| `doctor()` | Diagnostic | Probes WhatsApp process, WebView2 CDP port 9224, and storage readiness. |
| `list_chats(limit=200)` | Read | Lists active 1:1 and group conversations with unread counts and timestamps. |
| `read_chat(chat_id, limit=50)` | Read | Retrieves message history newest-first with cursor-based pagination. |
| `extract_recent(chat_id, hours=24)` | Read | Extracts all conversation messages within the last N hours. |
| `search_messages(query, chat_id=...)` | Read | Substring search across message bodies with optional filters. |
| `search_contacts(query)` | Read | Fast search for contacts and chats by name or phone fragment. |
| `get_chat_metadata(chat_id)` | Read | Retrieves group subject, description, creation date, admin roster, and participants. |
| `get_message_context(message_id)` | Read | Fetches contextual messages before and after a target message. |
| `send_file(chat_id, file_path, caption)` | Send | Sends documents, PDFs, CAD exports, high-res photos with original quality. |
| `send_message(chat_id, body)` | Send | Sends formatted text message to a resolved chat with human confirmation gating. |

---

## 🚀 Quick Start (Windows)

### 1. Prerequisites
- **Windows 10 or 11** (64-bit).
- **WhatsApp Desktop** installed from the [Microsoft Store](https://apps.microsoft.com/detail/9nksqgp7f2nh).
- **Python 3.12+** (or [Astral uv](https://docs.astral.sh/uv/)).

### 2. Enable Remote Debugging on WhatsApp Desktop
Open PowerShell as Administrator or regular user and execute:
```powershell
[Environment]::SetEnvironmentVariable("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--remote-debugging-port=9224", "User")
```
*Restart WhatsApp Desktop completely (`Stop-Process -Name "WhatsApp.Root" -Force` then run `start whatsapp:`).*

### 3. Installation
```powershell
# Clone repository
git clone https://github.com/Cristinacarolsouza/whatsapp-desktop-mcp-windows.git
cd whatsapp-desktop-mcp-windows

# Sync environment with uv
uv sync

# Run diagnostics
uv run whatsapp-desktop-mcp doctor
```

---

## ⚙️ MCP Client Configuration

### In Antigravity / Claude Desktop (`mcp_config.json`):

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "cmd.exe",
      "args": [
        "/c",
        "uv",
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

## 🔒 Security & Privacy Guarantees

- **Zero Plaintext Logging:** Outgoing messages and files are logged strictly as cryptographic SHA-256 hashes.
- **Sliding-Window Rate Limits:** 5 sends/minute and 30 sends/day prevent accidental bulk messaging.
- **Human-in-the-Loop Gating:** Every send action triggers an MCP elicitation modal displaying recipient JID and content for user confirmation.
- **Local Isolation:** 100% of data stays on your local machine; nothing is proxied to external servers.

---

## 📄 License

MIT License. Copyright (c) 2026 Cristina Carol Souza. See [LICENSE](LICENSE) for details.
