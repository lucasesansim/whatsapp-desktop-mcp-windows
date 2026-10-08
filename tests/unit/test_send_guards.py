"""Regression tests for recipient identity, content, confirmation and overlap."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.elicitation import AcceptedElicitation, DeclinedElicitation

from whatsapp_desktop_mcp import server
from whatsapp_desktop_mcp.exceptions import ChatHeaderMismatch
from whatsapp_desktop_mcp.models.chat import Chat
from whatsapp_desktop_mcp.models.contact import Jid
from whatsapp_desktop_mcp.models.coverage import Coverage
from whatsapp_desktop_mcp.models.send import ConfirmationSchema
from whatsapp_desktop_mcp.sender.guard import exclusive_send
from whatsapp_desktop_mcp.tools import send_file, send_message
from whatsapp_desktop_mcp.windows import scripts
from whatsapp_desktop_mcp.windows.sender import WindowsCDPTransport
from whatsapp_desktop_mcp.windows.verification import PendingSend, validate_jid

JID = "15550100001@c.us"
MSG = "true_15550100001@c.us_NEW"


def chat():
    return Chat(chat_id=1, jid=Jid.from_raw(JID), display_name="Ana", kind="direct", coverage=Coverage())


def record(**changes):
    value = dict(id=MSG, to=JID, fromMe=True, t=100, type="chat", body="Hola")
    value.update(changes)
    return value


def accepted(value=True):
    return SimpleNamespace(
        elicit=AsyncMock(return_value=AcceptedElicitation(data=ConfirmationSchema(confirm=value)))
    )


@pytest.mark.parametrize("changes", [
    {"to": "155501000010@c.us"}, {"to": "15550100001@g.us"}, {"to": None},
    {"fromMe": False}, {"fromMe": 1}, {"t": 99}, {"t": True}, {"t": "100"},
    {"t": float("nan")}, {"t": float("inf")},
    {"body": "Hola "}, {"body": "hola"}, {"body": "Hola\n"}, {"body": None},
    {"type": "document"}, {"id": ""}, {"id": None},
])
def test_other_message_does_not_verify(changes):
    assert PendingSend(JID, "Hola", 100).match(record(**changes)) is None


def test_exact_message_and_line_endings():
    assert PendingSend(JID, "Hola", 100).match(record()) == MSG
    assert PendingSend(JID, "a\r\nb", 100).match(record(body="a\nb")) == MSG


def test_identical_existing_message_does_not_verify():
    assert PendingSend(JID, "Hola", 100, {MSG}).match(record()) is None


def test_file_requires_exact_metadata_and_caption():
    pending = PendingSend(JID, "Informe", 100, filename="report.pdf", size=42)
    good = record(type="document", filename="report.pdf", size=42, caption="Informe")
    assert pending.match(good) == MSG
    for changes in ({"filename": "other.pdf"}, {"size": 43}, {"caption": "Informe "}, {"type": "chat"}):
        assert pending.match({**good, **changes}) is None


@pytest.mark.parametrize("value", ['1555@c.us";throw Error("x")//', "1555@evil.com", "", "Ana"])
def test_malformed_identifier_rejected(value):
    with pytest.raises(ValueError):
        validate_jid(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("info", [
    {}, {"activeJid": None, "headerTitle": "Ana"},
    {"activeJid": "15550100002@c.us", "headerTitle": "Ana"},
    {"activeJid": "15550100002@c.us", "headerTitle": "Ana Trabajo"},
    {"isMatchJid": True, "headerTitle": "Ana"},
])
async def test_names_or_untrusted_boolean_never_authorize_send(info):
    cdp = SimpleNamespace(connect=AsyncMock(), evaluate=AsyncMock(return_value=info))
    transport = WindowsCDPTransport(cdp)
    transport.open_chat = AsyncMock(return_value=False)
    with pytest.raises(ChatHeaderMismatch):
        await transport.assert_recipient(chat())


@pytest.mark.asyncio
async def test_exact_active_identifier_accepted():
    cdp = SimpleNamespace(connect=AsyncMock(), evaluate=AsyncMock(return_value={"activeJid": JID}))
    await WindowsCDPTransport(cdp).assert_recipient(chat())


@pytest.mark.asyncio
async def test_verification_excludes_old_and_unrelated_records():
    cdp = SimpleNamespace(evaluate=AsyncMock(return_value={
        "overflow": False, "rows": [
            record(id="old"), record(id="wrong", body="Other"),
            record(id="foreign", to="15550100002@c.us"), record(),
        ],
    }))
    transport = WindowsCDPTransport(cdp)
    transport._pending = PendingSend(JID, "Hola", 100, {"old"})
    assert await transport.verify_outgoing(chat(), "Hola", 100, 0) == MSG
    assert transport._pending is None


@pytest.mark.asyncio
async def test_ambiguous_identical_new_records_are_not_verified():
    cdp = SimpleNamespace(evaluate=AsyncMock(return_value={
        "overflow": False, "rows": [record(id="one"), record(id="two")],
    }))
    transport = WindowsCDPTransport(cdp)
    transport._pending = PendingSend(JID, "Hola", 100)
    assert await transport.verify_outgoing(chat(), "Hola", 100, 0) is None


@pytest.mark.asyncio
async def test_overflow_fails_closed():
    cdp = SimpleNamespace(evaluate=AsyncMock(return_value={"overflow": True, "rows": []}))
    transport = WindowsCDPTransport(cdp)
    transport._pending = PendingSend(JID, "Hola", 100)
    with pytest.raises(RuntimeError, match="complete"):
        await transport.verify_outgoing(chat(), "Hola", 100, 0)
    assert transport._pending is None


@pytest.mark.asyncio
async def test_declined_text_never_reaches_transport(monkeypatch):
    server.set_read_only_mode(False)
    monkeypatch.setattr(server.reader, "find_chat_by_id", AsyncMock(return_value=chat()))
    send = AsyncMock()
    monkeypatch.setattr(server.transport, "send_text", send)
    ctx = SimpleNamespace(elicit=AsyncMock(return_value=DeclinedElicitation()))
    result = await send_message.send_message(1, "Hola", ctx)
    assert result.status == "cancelled"
    send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["text", "file"])
async def test_old_skip_confirm_variable_cannot_bypass_confirmation(tool, tmp_path, monkeypatch):
    server.set_read_only_mode(False)
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_SKIP_CONFIRM", "1")
    monkeypatch.setattr(server.reader, "find_chat_by_id", AsyncMock(return_value=chat()))
    text_send, file_send = AsyncMock(), AsyncMock()
    monkeypatch.setattr(server.transport, "send_text", text_send)
    monkeypatch.setattr(server.transport, "send_file", file_send)
    with pytest.raises(ValueError, match="confirmation"):
        if tool == "text":
            await send_message.send_message(1, "Hola", None)
        else:
            path = tmp_path / "report.pdf"
            path.write_bytes(b"fake")
            await send_file.send_file(1, str(path), "", None)
    text_send.assert_not_awaited()
    file_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_text_is_sent_once_and_unverified_is_preserved(monkeypatch):
    server.set_read_only_mode(False)
    monkeypatch.setattr(server.reader, "find_chat_by_id", AsyncMock(return_value=chat()))
    send = AsyncMock(return_value=(False, 100))
    monkeypatch.setattr(server.transport, "send_text", send)
    monkeypatch.setattr(server.transport, "verify_outgoing", AsyncMock(return_value=None))
    ctx = accepted()
    result = await send_message.send_message(1, "Hola", ctx)
    assert result.status == "sent_unverified"
    send.assert_awaited_once()
    assert "do not retry" in result.verification_note.lower()


@pytest.mark.asyncio
async def test_timeout_does_not_retry_and_consumes_budget(monkeypatch):
    server.set_read_only_mode(False)
    monkeypatch.setenv("WHATSAPP_DESKTOP_MCP_RATE_PER_MIN", "1")
    monkeypatch.setattr(server.reader, "find_chat_by_id", AsyncMock(return_value=chat()))
    send = AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr(server.transport, "send_text", send)
    with pytest.raises(ValueError, match="do not retry"):
        await send_message.send_message(1, "Hola", accepted())
    with pytest.raises(ValueError, match="Rate limit"):
        await send_message.send_message(1, "Hola", accepted())
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_parallel_send_is_blocked_and_lock_is_released():
    async with exclusive_send():
        with pytest.raises(RuntimeError, match="in progress"):
            async with exclusive_send():
                pytest.fail("overlapping send accepted")
    async with exclusive_send():
        pass


@pytest.mark.asyncio
async def test_separate_process_cannot_send_while_locked():
    import sys

    code = """
import asyncio
from whatsapp_desktop_mcp.sender.guard import exclusive_send
async def main():
    try:
        async with exclusive_send(): return 3
    except RuntimeError: return 0
raise SystemExit(asyncio.run(main()))
"""
    async with exclusive_send():
        result = await asyncio.to_thread(
            subprocess.run, [sys.executable, "-c", code], capture_output=True, timeout=10,
        )
        assert result.returncode == 0, result.stderr.decode()
    # The OS lock is reusable after leaving the scope.
    async with exclusive_send():
        pass


@pytest.fixture
def node():
    executable = os.environ.get("TEST_NODE") or shutil.which("node")
    if not executable:
        pytest.skip("Node.js is needed to execute the actual CDP guard programs.")
    return executable


def run_js(node, program, **values):
    harness = """
const vm = require("node:vm");
const fs = require("node:fs");
const data = JSON.parse(fs.readFileSync(0, "utf8"));
let clicks = 0, insertions = 0;
const input = {innerText: data.draft || "", focus() {}};
const button = {disabled: false, getAttribute() {return null;}, click() {clicks++;}};
const icon = {closest() {return button;}};
let reads = 0;
const sandbox = {
  window: {require() {return {Chat: {getActive() {
    reads++; return {id: data.active};
  }}};}},
  document: {
    querySelectorAll() { return [{files: data.files || []}]; },
    querySelector(selector) {
      if (selector.includes("quoted-message")) return null;
      if (selector.includes("contenteditable")) return input;
      return icon;
    },
    execCommand(_, unused, body) { insertions++; input.innerText += body; return true; }
  }
};
let result = vm.runInNewContext(data.program, sandbox, {timeout: 1000});
console.log(JSON.stringify({result, clicks, insertions, draft: input.innerText}));
"""
    completed = subprocess.run(
        [node, "-e", harness], input=json.dumps({"program": program, **values}),
        text=True, encoding="utf-8", capture_output=True, check=True, timeout=5,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize("active", [None, "155501000010@c.us", {"_serialized": "15550100002@c.us"}])
def test_real_click_program_rejects_wrong_chat(node, active):
    result = run_js(node, scripts.click_send(JID, "Hola"), active=active, draft="Hola")
    assert result["result"] is False and result["clicks"] == 0


def test_real_click_program_accepts_object_identifier(node):
    result = run_js(node, scripts.click_send(JID, "Hola"),
                    active={"_serialized": JID}, draft="Hola")
    assert result["result"] is True and result["clicks"] == 1


def test_real_click_program_blocks_changed_body(node):
    result = run_js(node, scripts.click_send(JID, "Hola"), active=JID, draft="Hola extra")
    assert result["clicks"] == 0


def test_real_compose_program_preserves_existing_draft(node):
    result = run_js(node, scripts.compose_text(JID, "Hola"), active=JID, draft="Private draft")
    assert result["result"] is False and result["draft"] == "Private draft"
    assert result["insertions"] == 0


def test_real_program_handles_quotes_newlines_and_emoji(node):
    body = 'Hola "Ana"\n😊'
    result = run_js(node, scripts.compose_text(JID, body), active=JID, draft="")
    assert result["result"] is True and result["draft"] == body


@pytest.mark.parametrize("files", [
    [], [{"name": "wrong.pdf", "size": 42}],
    [{"name": "report.pdf", "size": 43}],
    [{"name": "report.pdf", "size": 42}, {"name": "extra.pdf", "size": 1}],
])
def test_real_attachment_click_blocks_unexpected_files(node, files):
    program = scripts.click_send(JID, "Informe", attachment=True, filename="report.pdf", size=42)
    result = run_js(node, program, active=JID, draft="Informe", files=files)
    assert result["result"] is False and result["clicks"] == 0


def test_real_attachment_click_accepts_exact_file_metadata(node):
    program = scripts.click_send(JID, "Informe", attachment=True, filename="report.pdf", size=42)
    result = run_js(node, program, active=JID, draft="Informe",
                    files=[{"name": "report.pdf", "size": 42}])
    assert result["result"] is True and result["clicks"] == 1


@pytest.mark.asyncio
async def test_actual_deadline_warns_without_retry(monkeypatch):
    server.set_read_only_mode(False)
    monkeypatch.setattr(server.reader, "find_chat_by_id", AsyncMock(return_value=chat()))
    original_timeout = asyncio.timeout
    monkeypatch.setattr(send_message.asyncio, "timeout", lambda _: original_timeout(0.001))
    async def delayed_send(*args):
        await asyncio.sleep(1)
    send = AsyncMock(side_effect=delayed_send)
    monkeypatch.setattr(server.transport, "send_text", send)
    with pytest.raises(ValueError, match="do not retry"):
        await send_message.send_message(1, "Hola", accepted())
    send.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["search_contacts", "search_messages"])
async def test_search_program_encodes_multiline_and_escape_sequences(node, method):
    from whatsapp_desktop_mcp.windows.idb_reader import IndexedDBReader

    # Quotes preceded by backslashes and actual newlines broke manual escaping.
    query = 'A\\\\"; globalThis.injected = true; //\nOtra línea'
    cdp = SimpleNamespace(connect=AsyncMock(), evaluate=AsyncMock(return_value=[]))
    await getattr(IndexedDBReader(cdp), method)(query)
    program = cdp.evaluate.call_args.args[0]
    check = """
const vm = require("node:vm");
const fs = require("node:fs");
const data = JSON.parse(fs.readFileSync(0, "utf8"));
new vm.Script(data.program);
const declaration = data.program.match(/const q = (.*);/)[1];
if (vm.runInNewContext(declaration) !== data.expected) process.exit(2);
"""
    subprocess.run(
        [node, "-e", check],
        input=json.dumps({"program": program, "expected": query.lower()}),
        text=True, encoding="utf-8", capture_output=True, check=True, timeout=5,
    )
