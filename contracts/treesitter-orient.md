---
id: greenbar-v0.5-treesitter-orient
goal: "Make `greenbar orient` polyglot: an optional tree-sitter extractor covering the languages graphify handles (JS/TS, Go, Rust, Java, C/C++, Kotlin, Swift, Ruby, C#) · measurable: with the extra installed, orient maps a non-Python repo; without it, orient still works Python-only · constraint: tree-sitter is an OPTIONAL extra — Greenbar core stays stdlib + PyYAML."
tier: scoped

non_goals:
  - "bundling tree-sitter into core deps (it is `pip install greenbar[treesitter]`)"
  - "full/precise cross-language resolution — still an approximate orientation map (name-based edges)"
  - "shipping per-language tags.scm query files — a compact node-type table covers the orientation need"

acceptance:
  - { id: A1, must: "with tree-sitter installed, orient extracts symbols from at least JS, Go, and one C-family language" }
  - { id: A2, must: "without tree-sitter installed, orient falls back to Python-only with no import error" }
  - { id: A3, must: "`build_graph` dispatches each file to the right extractor by extension (Python→ast, others→tree-sitter)" }
  - { id: A4, must: "a file in an unsupported language, or a tree-sitter parse failure, is skipped — never fatal" }
  - { id: A5, must: "the tree-sitter extractor is registered without touching the Python-ast core path (pluggable)" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-02 — orientation runs on demand; parse cost is bounded by repo size, not tuned here" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a test (tree-sitter tests skip cleanly when the extra is absent)" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "absence of the extra, unsupported files, and parse errors all degrade gracefully (Python-only / skip), never crash" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Greenbar v0.5 — polyglot `greenbar orient`

**Why.** v0.4's orient is Python-only (stdlib `ast`). graphify's reach is multi-language via
tree-sitter. This adds that reach — as an **optional extra**, so core stays dependency-light and
`orient` still works out of the box on Python.

**How.** A `TreeSitterExtractor` implements the same `Extractor` interface as the Python one, using
`tree-sitter-language-pack` (prebuilt grammars) + a compact node-type table (definition node types
→ kind; name via the `name` field or first identifier; references via call/invocation nodes).
`build_graph` dispatches each file to an extractor by extension. The extra is loaded lazily; if
it's not installed, orient runs Python-only with no error.

**DO NOT.** Put tree-sitter in core deps; crash when the extra is absent or a file won't parse;
overclaim precision — the cross-language graph is orientation-grade (name-based), an advisory
read-replica to verify against source.
