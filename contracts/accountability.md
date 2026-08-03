---
id: trellis-v0.8-accountability
goal: "Answer 'does the loop pay?': `trellis accountability` computes a defect-escape rate — of the changes that PASSED all gates, how many were later reverted (or flagged as incidents) · measurable: given git reverts + the gate history, it reports escapes / gated-changes and a caught-vs-escaped picture · constraint: dependency-light (git + history.jsonl only); reverts are an HONESTLY-LABELLED proxy, never claimed as ground-truth defects."
tier: scoped

non_goals:
  - "a true defect metric — reverts/incidents are proxies; the output must say so"
  - "an external incident-tracker integration — incidents come from a plain SHA list (--incidents)"
  - "judging ungoverned commits — only commits with a gate record are scored (ungoverned reverts are reported separately, not as escapes)"

acceptance:
  - { id: A1, must: "`trellis gate` records the commit SHA on its history event so a later revert can be linked to it" }
  - { id: A2, must: "accountability parses git reverts ('This reverts commit <sha>') and links each to the reverted commit" }
  - { id: A3, must: "escape = a reverted commit that had a PASSING gate record; escape_rate = escapes / gated-changes" }
  - { id: A4, must: "a reverted commit with NO gate record is counted as an ungoverned revert, NOT an escape" }
  - { id: A5, must: "an optional --incidents SHA list adds incident-based escapes; empty git/history yields a report, not a crash; output labels reverts as a proxy" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-03 — parsing git log + a jsonl history is not perf-sensitive" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "the proxy is labelled; ungoverned reverts are not counted as escapes; empty inputs never crash" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Trellis v0.8 — the accountability metric

**Why.** Every "AI review / spec" tool asserts it helps; none *measure* it. The differentiator:
answer, from data, "of everything our gates waved through, what fraction turned out bad?" That
number — the defect-escape rate — is CTO-legible and makes the loop accountable.

**How (honest + dependency-light).** `trellis gate` stamps the commit SHA on its history event.
`trellis accountability` reads git for reverts ("This reverts commit <sha>"), links each revert to
the reverted commit, and calls it an **escape** iff that commit had a passing gate record. Escape
rate = escapes / gated-changes. An optional `--incidents <sha-file>` folds in incident-linked
commits. Reverts are a **proxy** for defects (not every revert is a defect, not every defect is
reverted) — the output says so, and commits Trellis never gated are reported as *ungoverned*, not
as escapes.

**DO NOT.** Claim reverts are ground-truth defects; count ungoverned reverts as escapes; require an
external service; crash on an empty repo/history.
