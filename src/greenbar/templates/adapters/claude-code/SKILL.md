---
name: greenbar
description: Author a Greenbar contract for any non-trivial change, lint it, implement against it test-first, and run the tier's gates before pushing. Use when starting a feature, fix, or refactor in a repo that has a greenbar.yaml.
---

# Greenbar loop — author the contract, then let the gates prove it

Use this skill for any non-trivial change. It makes the agent produce the artifacts Greenbar
enforces, so defects surface at authoring and the PR can't merge with the process skipped.

## Procedure

1. **Orient.** Read the relevant code + any charter/PRD; recall project memory. Don't grep-and-go.
2. **Author the contract** at `contracts/<change-id>.md` — fill the frontmatter fully:
   - `goal` (one line: what · measurable bar · constraint), `tier` (blast radius),
   - `non_goals`, `acceptance` (binary, verifiable criteria),
   - `quality_axes`: for every profile you touch, declare every axis as `asserted` / `deferred`
     / `n_a`; every **asserted** axis needs a `must_have` **behavioral** KPI (not a coverage %).
3. **Lint it:** `greenbar lint contracts/<change-id>.md` — fix every error before writing code.
4. **Implement** against the contract: tests first (RED→GREEN), match surrounding style.
5. **Before you push:** `greenbar gate <tier> --contract contracts/<change-id>.md`. Fold every
   failure. For a `critical` tier, produce the review record the `review-record` gate requires
   (run your review panel and write `.greenbar/review-record.json`).
6. **Park HITL items** listed in the contract's `hitl:` (merges, releases, spend, external comms).
   Never self-approve them.

## Anti-patterns
- Writing code before `greenbar lint` passes.
- Asserting a quality axis with no behavioral KPI (the linter will fail you — good).
- Pushing before `greenbar gate` is green and letting CI/the reviewer catch it.
