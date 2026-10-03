---
id: greenbar-v0.6-design-lenses
goal: "Add a design-phase review: a pack of 5 independent discipline lenses (abstraction-contracts, distributed-invariants, systems-simplicity, evolutionary-design, domain-model) + a `design` tier + a deterministic ADR gate, run BEFORE implementation · measurable: `greenbar review --group design` runs only the design lenses and a `design` tier gates a design record + an ADR · constraint: lenses are discipline rubrics (not celebrity impersonations); tool-agnostic; dependency-light."
tier: scoped

non_goals:
  - "impersonating named people — lenses are distilled discipline heuristics, named by discipline"
  - "bundling a TLA+/model-checker — that's a documented `run:` recipe (tool-specific), not core code"
  - "auto-generating ADRs — the ADR gate CHECKS one exists/references the design, it doesn't write it"

acceptance:
  - { id: A1, must: "a lens can load its persona from a `persona_file`, so the 5-lens pack is reusable without inlining prompts" }
  - { id: A2, must: "`greenbar review --group design` runs ONLY lenses tagged group: design (code lenses excluded)" }
  - { id: A3, must: "the `builtin: adr` gate passes iff an ADR exists in the configured dir and (when required) references the contract id; else fails with a clear reason" }
  - { id: A4, must: "the 5 design persona files ship in the package and are copied by `greenbar init`" }
  - { id: A5, must: "absent group / absent persona_file / absent ADR dir all degrade gracefully (no crash)" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-03 — a lens-loader + ADR-presence check is not perf-sensitive" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "a missing persona_file / group / ADR dir yields a sensible fallback or a clear gate failure, never a crash" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Greenbar v0.6 — architecture design-lens pack

**Why.** Design is where a wrong call is cheapest to catch. This moves the multi-lens review
*earlier* — onto the design doc, before code — with five independent lenses distilled from durable
schools of software architecture, plus a deterministic ADR gate so every design-tier change leaves
a decision record.

**Discipline, not impersonation.** The lenses are named by discipline (abstraction-contracts,
distributed-invariants, systems-simplicity, evolutionary-design, domain-model) and carry the
school's *heuristics as a rubric* — not a claim to be the person. Real independence still comes
from running them as separate passes (and, ideally, cross-model); where a school has a formal tool
(TLA+ for invariants), wire the actual tool as a `run:` gate rather than a prompt.

**How.** Lenses gain `persona_file` (load the rubric from the pack) and `group` (so
`review --group design` runs only the design set). A `design` tier gates `[contract, adr,
design-review]`. `greenbar init` drops the 5 rubric files into `lenses/`.

**DO NOT.** Impersonate living people as authority; bundle a model checker into core; crash on a
missing persona_file / group / ADR dir; auto-write ADRs (the gate only checks one exists).
