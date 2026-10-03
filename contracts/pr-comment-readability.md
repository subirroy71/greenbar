---
id: greenbar-v0.10.1-pr-comment-readability
goal: "Make a failing PR comment readable at a glance · measurable: a failing deterministic lens shows the failure summary, not progress output, and counts read '1 lens' / '1 finding' · constraint: no change to verdicts, gating, or the record schema."
tier: scoped

non_goals:
  - "changing what passes or fails — presentation only"
  - "summarising LLM lens findings (they are already one line each)"

acceptance:
  - { id: A1, must: "a failing deterministic lens records an excerpt built from the tool's failure summary (pytest 'FAILED'/'ERROR' lines, else the last lines of output), never the leading progress output" }
  - { id: A2, must: "the excerpt is capped at 800 characters by whole lines (with an '… N more lines' marker), so its first line is never a fragment; progress dots and dividers never appear even without a summary line" }
  - { id: A3, must: "the PR comment shows a multi-line finding as one bullet line plus a collapsible <details> block holding the full text, so the list never breaks" }
  - { id: A4, must: "counts are pluralised correctly in the PR comment, `greenbar review` output and the review gate detail ('1 lens', '2 lenses', '1 finding')" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-10-03 — string formatting on small outputs" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1–A4 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "an excerpt of real pytest output (generated in the test) leads with the failing test's FAILED line, and the rendered comment's first bullet names it" }

hitl:
  - "merge to main"
---

# PR comment readability

**Why.** The first live PR comment for a failing run showed 800 characters of pytest progress dots
and cut off before the failure, inside a bullet that broke on the first newline. It also read
"1 lenses". The comment is the first page a design partner sees when something fails.
