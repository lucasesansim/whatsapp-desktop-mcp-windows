# WhatsApp Desktop MCP Instructions

Use this MCP server to query and control the official WhatsApp Desktop application on Windows.

## Capabilities & Tools
1. **Send Operations (Full Mode):**
   - `send_file(chat_id, file_path, caption)`: Sends a file attachment (PDF report, 3D render, technical drawing, image, document) in 100% original full resolution via document attachment. Automatically navigates and focuses the target conversation in the background.
   - `send_message(chat_id, body)`: Sends a text message to a resolved chat.
2. **Read Operations:**
   - `search_contacts(query)`: Finds contacts or groups by name/number fragment to obtain `chat_id`.
   - `list_chats(limit)`: Lists recent conversations with last message, unread count, and metadata.
   - `read_chat(chat_id, limit)`: Reads message history newest-first.
   - `extract_recent(chat_id, hours)`: Extracts conversation history for the last N hours.
   - `get_chat_metadata(chat_id)`: Retrieves group participants, subject, and admin status.
   - `search_messages(query)`: Substring search across message bodies.
   - `doctor()`: Verifies WhatsApp Desktop process, WebView2 CDP connection, and storage readiness.

## Regra de Ouro do Fluxo de Envio (Hábito Mandatório)
- **Anexo Primeiro, Texto Depois**: Ao compartilhar qualquer relatório, render, PDF, imagem técnica ou documento acompanhado de explicação ou mensagem contextual, **SEMPRE envie o anexo primeiro via `send_file`** (usando a legenda/caption para contexto imediato), e **só depois envie o texto complementar via `send_message`** (se necessário).
- **Por que isso é crítico?**: Enviar o anexo primeiro garante que o arquivo seja transmitido, processado e renderizado como âncora visual/documental no WhatsApp antes de textos adicionais, prevenindo perda de foco na interface, cancelamentos acidentais e desencontros no chat do cliente.

## Usage Guidelines
- Always resolve the recipient's `chat_id` via `search_contacts(query="...")` or `list_chats()` first.
- When sending renders, project sheets, or photos where quality matters, use `send_file` so they are delivered in original uncompressed high resolution.
- WhatsApp Desktop must be running on the computer.
