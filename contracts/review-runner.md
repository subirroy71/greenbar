---
id: trellis-v0.2-review-runner
goal: "Add `trellis review`: convene independent lenses on a change, each tracing the real diff, and emit `.trellis/review-record.json` · measurable: the `review` gate passes iff a fresh, non-BLOCK record for the current contract exists · constraint: provider-agnostic (shell-command lenses, no bundled LLM SDK), fail-closed."
tier: scoped

non_goals:
  - "bundling a specific LLM SDK — lenses are shell commands the user wires (claude / llm / aider / a script)"
  - "auto blast-radius classification from the diff (v0.3)"
  - "a hosted service — Trellis stays a local CLI + CI action"

acceptance:
  - { id: A1, must: "`trellis review` runs each configured lens independently and writes a review-record.json with per-lens verdicts" }
  - { id: A2, must: "a lens command that times out or emits no parseable verdict is recorded as ERROR, never silently SIGN (fail-closed)" }
  - { id: A3, must: "the `review` gate fails if the record is missing, stale (contract changed), or BLOCKED" }
  - { id: A4, must: "cross-model works: each lens carries its own command, so different lenses can target different models" }
  - { id: A5, must: "a rubber-stamp signal is computed (all lenses SIGN with zero findings) and can fail the gate" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: deferred, deferred_to: "lenses run in parallel; per-lens timeout bounds latency — perf tuning is out of scope" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "a broken/timed-out/unparseable lens is ERROR (fail-closed), never a false SIGN" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Trellis v0.2 — the review-panel runner

**Why.** v0.1 enforces that a review record *exists*; it can't produce one. `trellis review` turns
the ad-hoc "run a multi-persona panel by hand" into a reproducible artifact: independent lenses,
each tracing the real diff, verdict + findings collected into a record the `critical` tier gates on.

**Provider-agnostic by design.** A lens is a shell command. It receives the prompt (persona +
contract + diff) on stdin and prints its review ending in a JSON verdict; a `deterministic: true`
lens (a static analyzer) derives its verdict from the exit code instead. Cross-model = point
different lenses at different model CLIs. Trellis calls no LLM directly — it orchestrates whatever
you wire, which is what keeps it OSS-portable and dependency-light.

**Fail-closed.** A lens that times out, crashes, or emits no parseable verdict is ERROR — it never
counts as a pass. The record records a context hash so you can prove which tree was reviewed
(the "reviewer read the wrong worktree" failure mode we've hit before).

**DO NOT.** Bundle an LLM SDK; let an unparseable lens default to SIGN; let a stale record (for an
old version of the contract) satisfy the gate.
