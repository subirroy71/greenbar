---
id: greenbar-v0.9-pr-native
goal: "Make Greenbar PR-native: `greenbar render` turns the latest gate + review artifacts into a Markdown PR summary, and a shipped GitHub workflow runs the gate (required check) + upserts that summary as a single PR comment · measurable: render produces a comment showing the gate table + review verdicts/findings; the workflow blocks merge on gate failure and updates one comment (no spam) · constraint: no hosted service — a reusable Action + the repo's GITHUB_TOKEN; dependency-light."
tier: scoped

non_goals:
  - "a hosted GitHub App / server — Greenbar stays a CLI + CI Action (same PR UX, no server to run)"
  - "inventing findings — render only formats what `gate`/`review` already produced"
  - "posting the comment from the CLI — the CLI renders Markdown; the Action posts/updates it"

acceptance:
  - { id: A1, must: "`greenbar render` renders the most-recent gate event as a gate table (pass/fail per gate + overall)" }
  - { id: A2, must: "render includes each review record's verdict, lens count, and findings; and flags an all-SIGN/zero-findings rubber stamp" }
  - { id: A3, must: "render embeds a stable marker so a workflow can UPDATE one comment instead of spamming new ones" }
  - { id: A4, must: "a shipped GitHub workflow template runs `greenbar gate --auto` as a required check and upserts the rendered comment" }
  - { id: A5, must: "render degrades gracefully — no gate event / no review records yields a valid comment, not a crash" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-03 — formatting a few JSON artifacts to Markdown is not perf-sensitive" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "missing/partial artifacts render a sensible comment, never a crash" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Greenbar v0.9 — PR-native (Action, not a hosted App)

**Why.** Everything is terminal-only today. The adoption/visibility win is the PR surface: a
required check that blocks merge, and one clear comment showing what the gates + review found.

**How (no server).** A hosted GitHub App needs infrastructure Greenbar shouldn't own. Instead:
`greenbar render` formats the latest gate event + review record(s) into Markdown (with a stable
marker), and a shipped **GitHub Actions workflow** runs `greenbar gate --auto` (the required check)
and upserts that Markdown as a single PR comment using the repo's `GITHUB_TOKEN`. Same PR UX as an
App; nothing to host; consistent with Greenbar being a CLI + CI tool.

**DO NOT.** Turn Greenbar into a hosted service; render findings that `gate`/`review` didn't produce;
post from the CLI (separation: CLI renders, Action posts); crash on missing artifacts.
