"""Agent-native Greenbar — a minimal MCP server over stdio (pure stdlib).

MCP's stdio transport is newline-delimited JSON-RPC 2.0. This implements the
minimal surface real clients (Claude Code, Cursor) use — `initialize`,
`tools/list`, `tools/call`, `ping` — with no SDK dependency, dispatching to the
existing Greenbar library functions. Wire it in with e.g.
`claude mcp add greenbar -- greenbar mcp`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import __version__

PROTOCOL_VERSION = "2025-06-18"


# --- tool handlers (reuse the library; each returns text) --------------------

def _orient(args: dict) -> str:
    from .orient import build_graph, rank_symbols, render_map
    g = build_graph(args.get("path") or ".")
    focus = None
    base = args.get("diff_base")
    if base is not None:
        from .classify import git_numstat
        focus = set(git_numstat(base).files)
    ranked = rank_symbols(g, focus_files=focus)
    header = (f"# orientation for {len(focus)} changed file(s) · {len(g.symbols)} symbols\n\n"
              if focus else f"# repo map · {len(g.symbols)} symbols\n\n")
    return header + render_map(ranked, budget_tokens=int(args.get("budget", 1200)))


def _lint(args: dict) -> str:
    from .contract import parse_contract, validate_contract
    from .config import load_config
    meta, _ = parse_contract(Path(args["contract"]).read_text())
    try:
        cfg = load_config(args.get("config"))
        axes, tiers = cfg.axes, list(cfg.tiers)
    except Exception:  # noqa: BLE001
        axes, tiers = {"C": ["correctness", "reasonableness"]}, None
    findings = validate_contract(meta, axes, tiers=tiers)
    if not findings:
        return f"lint OK — {args['contract']} is well-formed."
    lines = [f"{f.code} [{f.level}] {f.message}" for f in findings]
    errors = sum(1 for f in findings if f.level == "error")
    return f"{len(findings)} finding(s), {errors} error(s):\n" + "\n".join(lines)


def _classify(args: dict) -> str:
    from .classify import git_numstat, classify
    from .config import load_config
    stat = git_numstat(args.get("diff_base"))
    try:
        rules = load_config(args.get("config")).raw.get("classify") or {}
    except Exception:  # noqa: BLE001
        rules = {}
    tier, why = classify(stat, rules)
    return (f"tier: {tier}\n  files={len(stat.files)} lines={stat.total_lines} "
            f"(+{stat.added}/-{stat.removed})\n  {why}")


def _draft(args: dict) -> str:
    from .draft import parse_prd, build_contract
    from .config import load_config
    text = args.get("prd")
    if text is None and args.get("prd_file"):
        text = Path(args["prd_file"]).read_text()
    if not text:
        raise ValueError("provide `prd` (text) or `prd_file` (path)")
    try:
        axes = load_config(args.get("config")).axes or {"C": ["correctness", "reasonableness"]}
    except Exception:  # noqa: BLE001
        axes = {"C": ["correctness", "reasonableness"]}
    parsed = parse_prd(text)
    cid = args.get("id") or "drafted-contract"
    return build_contract(parsed, cid, args.get("tier") or "scoped", axes, prd_body=text)


def _gate(args: dict) -> str:
    from .config import load_config
    from .gates import gate_event, run_tier
    from .history import current_commit, record_event
    cfg = load_config(args.get("config"))
    tier = args.get("tier") or "scoped"
    results = run_tier(tier, cfg, args.get("contract"))
    record_event(gate_event(tier, args.get("contract"), results, current_commit()))
    ok = sum(1 for r in results if r.ok)
    lines = [f"{'PASS' if r.ok else 'FAIL'}  {r.name}" + (f" — {r.detail}" if r.detail else "")
             for r in results]
    return f"gate '{tier}': {ok}/{len(results)} passed\n" + "\n".join(lines)


def _report(args: dict) -> str:
    from .history import read_events
    from .report import aggregate, format_report
    return format_report(aggregate(read_events(args.get("history", ".greenbar/history.jsonl"))))


TOOLS: List[dict] = [
    {"name": "greenbar_orient", "handler": _orient,
     "description": "Build a symbol map of the repo (ranked by relevance). Pass diff_base to focus on changed files.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "root to scan (default '.')"},
         "diff_base": {"type": "string", "description": "git ref; focus the map on files changed vs it"},
         "budget": {"type": "integer", "description": "token budget for the map (default 1200)"}}}},
    {"name": "greenbar_lint", "handler": _lint,
     "description": "Validate a Greenbar contract file (goal/acceptance/quality_axes/KPI rules).",
     "inputSchema": {"type": "object", "required": ["contract"], "properties": {
         "contract": {"type": "string", "description": "path to the contract .md"},
         "config": {"type": "string"}}}},
    {"name": "greenbar_classify", "handler": _classify,
     "description": "Classify the change's blast radius into a tier (design/trivial/scoped/critical).",
     "inputSchema": {"type": "object", "properties": {
         "diff_base": {"type": "string", "description": "git ref to diff against (default: staged/working)"},
         "config": {"type": "string"}}}},
    {"name": "greenbar_draft", "handler": _draft,
     "description": "Draft a contract from PRD text (heuristic). Returns the contract markdown.",
     "inputSchema": {"type": "object", "properties": {
         "prd": {"type": "string", "description": "PRD text"},
         "prd_file": {"type": "string", "description": "path to a PRD file (alternative to prd)"},
         "id": {"type": "string"}, "tier": {"type": "string"}, "config": {"type": "string"}}}},
    {"name": "greenbar_gate", "handler": _gate,
     "description": "Run a tier's gates (contract/review/adr/tests/…). Reports pass/fail per gate.",
     "inputSchema": {"type": "object", "properties": {
         "tier": {"type": "string", "description": "tier to run (default 'scoped')"},
         "contract": {"type": "string"}, "config": {"type": "string"}}}},
    {"name": "greenbar_report", "handler": _report,
     "description": "Summarize the recorded gate/review history (pass-rate, verdicts, rubber-stamp rate).",
     "inputSchema": {"type": "object", "properties": {
         "history": {"type": "string", "description": "path to history.jsonl (default .greenbar/history.jsonl)"}}}},
]

_BY_NAME: Dict[str, Callable[[dict], str]] = {t["name"]: t["handler"] for t in TOOLS}


# --- JSON-RPC dispatch -------------------------------------------------------

def _result(mid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _text(s: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": s}], "isError": is_error}


def handle(msg: dict) -> Optional[dict]:
    """Map one JSON-RPC message to its response (or None for notifications)."""
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        return _result(mid, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "greenbar", "version": __version__}})
    if method == "tools/list":
        return _result(mid, {"tools": [{k: t[k] for k in ("name", "description", "inputSchema")}
                                       for t in TOOLS]})
    if method == "tools/call":
        name = params.get("name")
        handler = _BY_NAME.get(name)
        if handler is None:
            return _result(mid, _text(f"unknown tool: {name}", is_error=True))
        try:
            return _result(mid, _text(handler(params.get("arguments") or {})))
        except Exception as exc:  # noqa: BLE001 — tool errors are in-band, never fatal
            return _result(mid, _text(f"{type(exc).__name__}: {exc}", is_error=True))
    if method == "ping":
        return _result(mid, {})
    if method and method.startswith("notifications/"):
        return None  # notifications get no response
    if mid is None:
        return None  # any other notification
    return _error(mid, -32601, f"method not found: {method}")


def serve(stdin=None, stdout=None) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip malformed lines, keep serving
        resp = handle(msg)
        if resp is not None:
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
    return 0
