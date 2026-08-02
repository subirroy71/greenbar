---
id: trellis-v0.3-metrics-and-autotier
goal: "Measure the loop and auto-scale it: `trellis report` aggregates gate/review history (pass-rate, verdicts, rubber-stamp trend) and `trellis classify` infers a change's tier from its diff (so `trellis gate --auto` picks the right rigor) · measurable: report reflects logged runs, classify maps a diff to a tier by first-matching rule · constraint: dependency-light, honest metrics (proxies labelled as proxies)."
tier: scoped

non_goals:
  - "a hosted dashboard — report prints to the terminal + `--json`"
  - "direct-API LLM lens providers (stays out to keep dependency-light; the command provider covers it)"
  - "a true defect-escape metric (needs prod linkage); v0.3 ships an honestly-labelled proxy only"

acceptance:
  - { id: A1, must: "`trellis gate` and `trellis review` append a structured event to .trellis/history.jsonl" }
  - { id: A2, must: "`trellis report` aggregates the history: gate pass-rate + failures-by-gate, review verdict distribution + rubber-stamp rate" }
  - { id: A3, must: "`trellis classify` maps a diff to a tier via first-matching config rule (path globs + file/line thresholds), else the default" }
  - { id: A4, must: "`trellis gate --auto` classifies the diff and runs the inferred tier" }
  - { id: A5, must: "a rule with no conditions never matches (no accidental catch-all); an empty history yields a report, not a crash" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-02 — aggregating a jsonl log + glob-matching a diff is not perf-sensitive" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "empty/absent history and a no-condition rule are handled gracefully (no crash, no false catch-all)" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Trellis v0.3 — measure the loop + auto-scale it

**Why.** Two named gaps remain: the loop isn't *measured* (is the ceremony paying?), and the tier
is a human judgement call (so rigor doesn't auto-scale to blast radius). v0.3 closes both.

**`trellis report`** reads a local `.trellis/history.jsonl` that every `gate`/`review` appends to,
and surfaces gate pass-rate, failures-by-gate, review verdict distribution, and the rubber-stamp
rate over time. Metrics that can only be proxies (defect-escape) are labelled as proxies.

**`trellis classify`** infers a change's tier from its diff via first-matching rules (path globs +
file/line thresholds). `trellis gate --auto` classifies then runs that tier — so a typo runs the
`trivial` gates and a migration/auth change runs `critical`, without anyone deciding.

**DO NOT.** Add heavy deps; let a rule with no conditions become an accidental catch-all; crash on
an empty/absent history; overclaim the defect-escape proxy as a true metric.
