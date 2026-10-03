"""v0.10 — the MCP server (dispatch tested without real stdio)."""
import io
import json

from greenbar import __version__
from greenbar.mcp_server import handle, serve, TOOLS


def _req(method, params=None, mid=1):
    return {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}


class TestProtocol:
    def test_initialize_reports_capabilities_and_server_info(self):  # A1
        r = handle(_req("initialize", {"protocolVersion": "2025-06-18"}))["result"]
        assert r["protocolVersion"] == "2025-06-18"
        assert "tools" in r["capabilities"]
        assert r["serverInfo"] == {"name": "greenbar", "version": __version__}

    def test_tools_list_exposes_schema(self):  # A2
        tools = handle(_req("tools/list"))["result"]["tools"]
        names = {t["name"] for t in tools}
        assert {"greenbar_orient", "greenbar_lint", "greenbar_classify", "greenbar_draft"} <= names
        for t in tools:
            assert t["description"] and t["inputSchema"]["type"] == "object"

    def test_ping(self):
        assert handle(_req("ping"))["result"] == {}

    def test_unknown_method_is_jsonrpc_error(self):  # A4
        r = handle(_req("does/not/exist"))
        assert r["error"]["code"] == -32601

    def test_notification_gets_no_response(self):  # A4
        assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


class TestToolsCall:
    def test_known_tool_returns_text(self):  # A3
        r = handle(_req("tools/call", {"name": "greenbar_draft",
                                       "arguments": {"prd": "# Goal\nDo X\n## Acceptance\n- must Y"}}))["result"]
        assert r["content"][0]["type"] == "text" and "id:" in r["content"][0]["text"]
        assert not r.get("isError")

    def test_unknown_tool_is_in_band_error(self):  # A3
        r = handle(_req("tools/call", {"name": "nope", "arguments": {}}))["result"]
        assert r["isError"] and "unknown tool" in r["content"][0]["text"]

    def test_raising_tool_degrades_gracefully(self):  # A5 — missing required contract path
        r = handle(_req("tools/call", {"name": "greenbar_lint",
                                       "arguments": {"contract": "/no/such/file.md"}}))["result"]
        assert r["isError"] and "content" in r  # error text, no crash

    def test_orient_runs_on_this_repo(self):
        r = handle(_req("tools/call", {"name": "greenbar_orient",
                                       "arguments": {"path": "src/greenbar", "budget": 400}}))["result"]
        assert not r.get("isError") and "symbols" in r["content"][0]["text"]


class TestServeLoop:
    def test_serve_reads_lines_and_skips_malformed(self):  # A5
        stdin = io.StringIO(
            json.dumps(_req("initialize")) + "\n"
            "{ not json\n"                       # skipped, loop survives
            + json.dumps(_req("tools/list", mid=2)) + "\n"
            + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        out = io.StringIO()
        assert serve(stdin, out) == 0
        replies = [json.loads(l) for l in out.getvalue().splitlines()]
        assert [r["id"] for r in replies] == [1, 2]  # init + list; malformed & notification produced nothing


def test_every_tool_is_dispatchable():
    listed = {t["name"] for t in handle(_req("tools/list"))["result"]["tools"]}
    assert listed == {t["name"] for t in TOOLS}
