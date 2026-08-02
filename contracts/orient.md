---
id: trellis-v0.4-orient
goal: "Add `trellis orient`: build a symbol graph of the repo and emit a token-bounded, rank-ordered code map an agent reads to orient before editing — focusable on a diff · measurable: orient returns the highest-ranked symbols within a token budget, and --diff biases toward changed files · constraint: dependency-light (stdlib `ast` for Python in core; other languages via an optional extractor), never crash on unparseable files."
tier: scoped

non_goals:
  - "full cross-file name resolution / a type-accurate graph — this is an approximate ranking map (like a repo map), not a compiler"
  - "bundling tree-sitter in core — Python works via stdlib ast; other languages are a pluggable extractor / optional extra"
  - "persisting the graph — orient builds it on demand (a v0.5 cache is out of scope)"

acceptance:
  - { id: A1, must: "`trellis orient` lists ranked symbols (name + file:line + signature) within a token budget" }
  - { id: A2, must: "`trellis orient --diff <d>` biases the ranking toward symbols in the changed files (personalized rank)" }
  - { id: A3, must: "a syntactically-broken source file is skipped, not fatal (orient still returns a map)" }
  - { id: A4, must: "the extractor is pluggable: Python via stdlib ast in core, and adding a language needs no core change" }
  - { id: A5, must: "the map fits the budget (never emits more than ~budget tokens of symbols)" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: deferred, deferred_to: "a persisted/cached graph is v0.5; on-demand build is fine for orientation" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "broken/empty/no-symbol inputs yield a sensible (possibly empty) map, never a crash" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Trellis v0.4 — `trellis orient`

**Why.** A code-map orientation step is the one big rtscale-loop capability Trellis lacked. It
collapses "read 15k tokens of files to find where to look" into a compact, ranked map — and,
focused on a diff, it answers "what does THIS change touch and connect to."

**How (dependency-light).** Parse the repo's Python with the stdlib `ast` module into a symbol
graph (defs as nodes; name-based call/reference edges). Rank with a personalized PageRank —
personalization concentrated on symbols in the changed files when `--diff` is given, else uniform
— so central *and* change-adjacent symbols float to the top. Render the top symbols (file:line +
signature) until a token budget is hit. The extractor is a small interface; tree-sitter / other
languages plug in as an optional extra without touching core.

**DO NOT.** Add heavy deps to core; crash on a malformed source file; emit past the token budget;
overclaim precision — this is an approximate orientation map, an advisory read-replica of the code
(verify against the source before acting), exactly the discipline graphify uses.
