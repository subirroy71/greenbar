---
# ── Greenbar contract (machine-checked frontmatter) ──────────────────────────────
id: example-feature
goal: "One line: what · the measurable bar · the constraint."
tier: scoped                       # must be a tier defined in greenbar.yaml

non_goals:                         # explicit out-of-scope (warns if missing)
  - "what this change deliberately does NOT do"

acceptance:                        # binary, independently-verifiable criteria
  - id: A1
    must: "a statement that is true or false, not 'better' or 'nicer'"
  - id: A2
    must: "another verifiable criterion"

quality_axes:
  profiles: [C]                    # which profiles this change touches (see greenbar.yaml `axes`)
  axes:
    # Every axis of every declared profile must appear here as asserted / deferred / n_a.
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: deferred, deferred_to: "perf-harness (issue #123)" }
  kpis:
    # Every ASSERTED axis needs at least one must_have KPI — a behavioral target, not a coverage %.
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "0 failing acceptance criteria" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "no fabricated/degenerate outputs on the edge set" }

hitl:                              # human checkpoints for anything irreversible
  - "merge to main"
---

# Context / method (prose — not machine-checked, but this is where the thinking lives)

Why this change, how it's approached, what's already established, the method (measure → implement
→ verify), and the DO-NOT list. Greenbar lints the frontmatter; the reviewer reads this.
