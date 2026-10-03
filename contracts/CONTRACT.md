---
id: greenbar-v0.1-enforcement-core
goal: "Ship the enforcement core: a machine-checked contract linter + a tiered gate runner that exits non-zero when a tier's gates fail · measurable: `greenbar gate scoped` blocks a bad contract in CI · constraint: dependency-light (stdlib + PyYAML), tool-agnostic."
tier: scoped

non_goals:
  - "the LLM review-panel runner (that's v0.2 — the `review-record` gate only checks the artifact exists)"
  - "auto blast-radius classification from the diff (v0.3)"
  - "language support beyond a generic `run:`/`requires_file:` gate"

acceptance:
  - { id: A1, must: "`greenbar lint` exits non-zero on a contract whose asserted axis has no must_have KPI" }
  - { id: A2, must: "`greenbar gate <tier>` exits non-zero iff any required gate fails" }
  - { id: A3, must: "`greenbar init` scaffolds a valid greenbar.yaml + example contract that lints clean" }
  - { id: A4, must: "the tool is dependency-light: stdlib + PyYAML only" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-07-28 — a lint/gate CLI over small YAML is not perf-sensitive" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "acceptance A1-A4 all covered by passing tests" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "malformed contract → a clear finding, never a stack trace (gate returns a failure, not a crash)" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Greenbar v0.1 — enforcement core

**Why.** Advisory workflows generate rigor but don't guarantee it. The core move is to make the
contract machine-checkable and the gates CI-blocking, so following the process is the path of
least resistance (a green build) and skipping it is a red one.

**Method.** TDD the validator first (it's the crown jewel — the asserted-axis-needs-a-KPI rule),
then the gate runner (three kinds: builtin/run/requires_file), then the CLI, then dogfood: this
repo carries its own `greenbar.yaml` + this contract and runs `greenbar gate scoped` in CI.

**DO NOT.** Add heavy deps; couple to one coding tool; let a malformed contract crash the gate
(it must fail closed to a clear finding).
