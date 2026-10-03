---
id: greenbar-v0.10.1-record-job-resilience
goal: "The post-merge record job survives GitHub API hiccups · measurable: a transient API failure is retried, an error body is never used as a commit SHA, and a persistent failure ends with a clear 're-run this job' error · constraint: workflow-only, no change to what gets recorded."
tier: scoped

non_goals:
  - "recording direct pushes — they stay ungoverned by design"
  - "changing the note format or the accountability metric"

acceptance:
  - { id: A1, must: "both GitHub API lookups in the record job are retried 3 times with backoff before giving up" }
  - { id: A2, must: "a PR head that is not a 40-character hex SHA is rejected with an error, never written into a note" }
  - { id: A3, must: "when the API stays unavailable the job fails with a message telling the maintainer to re-run it; a commit with no PR still exits cleanly as ungoverned" }
  - { id: A4, must: "the shipped template and this repo's workflow carry the same record-job logic" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-10-03 — at most ~30s of retry backoff on a post-merge job" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "a simulated gh (ok / down / garbage / no PR) yields: note data / re-run error / re-run error / ungoverned exit" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "the next real merge records its note on the landed commit" }

hitl:
  - "merge to main"
---

# Record job resilience

**Why.** After PR #2 merged, GitHub's API returned "No server is currently available"; the job
captured that error body as the PR head SHA and crashed building a URL from it. The re-run
succeeded, but the job should retry and fail clearly on its own.
