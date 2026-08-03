---
id: trellis-v0.10-mcp-server
goal: "Make Trellis agent-native: `trellis mcp` runs an MCP (Model Context Protocol) server over stdio exposing orient / lint / classify / draft / gate / report as tools any coding agent (Claude Code, Cursor) can call · measurable: the server answers initialize + tools/list + tools/call per JSON-RPC 2.0, and each tool returns Trellis output · constraint: pure stdlib (no MCP SDK dependency); dependency-light."
tier: scoped

non_goals:
  - "depending on an MCP SDK — the stdio JSON-RPC transport is small enough to implement in stdlib"
  - "HTTP/SSE transport — stdio only (what Claude Code / Cursor use for local servers)"
  - "exposing every command — a focused, agent-useful toolset (orient/lint/classify/draft/gate/report)"

acceptance:
  - { id: A1, must: "an `initialize` request returns protocolVersion + capabilities.tools + serverInfo" }
  - { id: A2, must: "a `tools/list` request returns each tool's name, description, and inputSchema" }
  - { id: A3, must: "a `tools/call` for a known tool returns its Trellis output as text content; an unknown tool returns isError content (not a JSON-RPC crash)" }
  - { id: A4, must: "notifications (no id) get no response; an unknown method with an id returns a JSON-RPC method-not-found error" }
  - { id: A5, must: "a tool handler that raises returns an isError content item, never taking the server down; malformed JSON lines are skipped" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-03 — a stdio JSON-RPC dispatch loop is not perf-sensitive" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test (dispatch tested without real stdio)" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "a raising tool / unknown tool / unknown method / malformed line all degrade gracefully, never crash the loop" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Trellis v0.10 — the MCP server (agent-native)

**Why.** The industry is moving to agentic coding; the strategic position is *the governance layer
agents call*. An MCP server lets any agent (Claude Code, Cursor, …) `orient` in the code, `lint` a
contract, `classify` a change, `draft` a contract from a PRD, `gate`, and read the `report` — as
first-class tools, mid-task.

**How (pure stdlib).** MCP's stdio transport is newline-delimited JSON-RPC 2.0. `trellis mcp`
implements the minimal server (`initialize`, `tools/list`, `tools/call`, `ping`) with no SDK
dependency, reusing the existing Trellis library functions as tool handlers. Wire it into an agent
with one line (e.g. `claude mcp add trellis -- trellis mcp`).

**DO NOT.** Add an MCP SDK to core; crash the loop on a raising tool / unknown method / malformed
line (all in-band errors); expose secrets or write outside the repo from a tool.
