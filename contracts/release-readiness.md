---
id: greenbar-v0.10-release-readiness
goal: "Make the first release usable by design partners: light mode for docs, agent setup in one command, an honest README, and a verified quickstart · measurable: a clean install completes the README quickstart end to end and a docs-only change passes without a contract · constraint: light mode must not let code changes skip a contract."
tier: scoped

non_goals:
  - "Spec Kit / OpenSpec contract sources, agent hooks, policy packs — roadmap, after design-partner feedback"
  - "monetization or hosted services"
  - "light mode for small code diffs — an agent could split work into tiny PRs to dodge the contract"

acceptance:
  - { id: A1, must: "in every preset the trivial tier has no contract gate but still runs lint (fmt for rust) and test" }
  - { id: A2, must: "preset classify rules send prose-doc-only diffs (.md/.rst) to trivial, any diff touching contracts/ to scoped, and any code diff — including code under docs/ or a 1-line change — to a non-trivial tier" }
  - { id: A3, must: "a tier that defines no gates fails instead of passing vacuously" }
  - { id: A4, must: "`greenbar init --agent claude-code|cursor` installs the skill at .claude/skills/greenbar/SKILL.md and the rule at .cursor/rules/greenbar.mdc, never overwriting an existing file" }
  - { id: A5, must: "`greenbar draft` uses the first line under a '## Goal' (or Objective / Problem) heading as the goal when no labelled goal line exists" }
  - { id: A7, must: "classification sees old paths: a rename (git numstat with --no-renames, numstat rename notation, or unified-diff rename lines) and a deletion each count the original path, so moving or deleting code is never a docs-only change; local classification includes untracked files repo-wide, from any subdirectory (except .greenbar/), the unified-diff parser sees empty added/deleted files and never mistakes a removed '-- ' line for a header or the next file's headers for content (hunks are bounded by their @@ counts, with or without git headers), and edits to reviewer prompts (any lenses/ directory) and agent instructions (CLAUDE.md, AGENTS.md, .claude/, .cursor/) are scoped, not light" }
  - { id: A6, must: "the README claims match the code: no CLAUDE.md snippet claim, draft TODOs and the revert-based escape-rate proxy are stated, and a design-partner call is present" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-10-03 — config and CLI scaffolding, no runtime hot path" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1–A5 and A7 each covered by a passing test; the README quickstart completes on a clean Python 3.11 install" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "a real cross-model review lens (claude -p) runs on this change and every BLOCK finding is resolved or answered" }

hitl:
  - "merge to main"
  - "publish to PyPI"
---

# Release readiness

**Why.** The plan's first step is a release that design partners can install and keep using. The
biggest adoption risk in the research was ceremony fatigue, so docs-only changes now need no
contract, while every code change still does. Agent setup and an honest, verified README remove
first-session friction.

**Method.** A real `claude -p` review lens ran on the first draft of this change and blocked it:
light mode also covered small code diffs (a contract-dodging route), the work had no contract of its
own, and a test had lost its exit-code check. A second run caught that `docs/**` let code under
docs/ ride light mode, and that `init --agent` would write through a dangling symlink. All were
fixed with regression tests. A third run found that a rename (`src/app.py → docs/app.md`) or a deletion
was classified by its new path only — a pre-existing parser gap that light mode turned into a bypass. A fourth run found local untracked
files, empty files and removed `-- ` lines slipping past the parser, and reviewer-prompt edits
counting as docs; all fixed with tests.

**Known issues (answered, not fixed — both fail closed or need an attacker with repo write).**
- An empty diff classifies as the default tier (`scoped`) rather than `trivial`: there is nothing
  to call docs-only, so it takes the stricter path. Intended.
- `init --agent` checks the final target for a symlink but not a symlinked *parent* directory, and
  a dangling parent symlink makes `mkdir` raise instead of skipping. Planting either requires write
  access to the repo, at which point the instructions file is already editable.
