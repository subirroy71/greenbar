# Changelog

All notable changes to Greenbar are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Greenbar adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-10-03
First tagged and PyPI-published release (v0.1–v0.9 were developed on `main` but never tagged).

### Changed — renamed from Trellis to Greenbar
- The project was developed as "Trellis" (`trellis-loop`). Before its first release it was renamed
  to avoid collisions with other AI-coding projects of that name: the package and CLI are now
  `greenbar`, the config is `greenbar.yaml`, local state lives in `.greenbar/`, durable history in
  `refs/notes/greenbar`, MCP tools are `greenbar_*`, the PR declaration is `Greenbar-Contract:`,
  and the commit override is `GREENBAR_COMMIT`. Entries below use the new names.

### Fixed — enforcement hardening (the cheapest green build no longer skips the rigor)
- `greenbar lint` rejects contracts that still carry scaffold placeholders (`TODO`/`TBD`/`FIXME`
  at the start of a goal, non-goal, acceptance criterion, axis or KPI target; C012), a `tier` not
  defined in `greenbar.yaml` (C013), and a `must_have` KPI with no target (C014). An unfilled
  `greenbar draft` contract no longer passes the gate.
- `greenbar lint` on a file without frontmatter is a clean C000 failure, not a traceback.
- The `review` gate checks code freshness: the record now carries a content fingerprint of the
  tracked tree, and the gate fails as STALE if any tracked file changed since the review
  (committing the reviewed content keeps it fresh). Previously only the contract was compared.
- A review with zero lenses is `NO_LENSES` — `greenbar review` exits 1 and the gate fails —
  instead of a vacuous PASS.
- `run:` gates time out (gate `timeout_s`, top-level `gate_timeout_s`, default 1800s) instead of
  hanging CI or an agent's MCP call.
- Preset and template deterministic lenses no longer end in `|| true` (they always signed off).
- The shipped PR workflow never falls back to an arbitrary contract (`ls -t`): a PR binds one via
  `Greenbar-Contract: <path>` in its description or by changing exactly one contract. Gates run
  with the base branch's `greenbar.yaml`, so a PR can't loosen its own policy. PR-controlled values
  reach the shell via env vars, not `${{ }}` interpolation.

### Added
- **Light mode:** in every preset the `trivial` tier needs no contract (still lint + test), and
  only prose-doc diffs (`.md`/`.rst`) classify as trivial — any code change, even under `docs/`, needs a contract, so an agent can't
  dodge one by splitting work into tiny PRs. A diff touching `contracts/` classifies as `scoped`
  so the contract gets linted. A tier with no gates now fails rather than passing vacuously.
- `greenbar init --agent claude-code|cursor` installs the agent instructions where each tool loads
  them (`.claude/skills/greenbar/SKILL.md`, `.cursor/rules/greenbar.mdc`) and prints the
  `claude mcp add` line.
- Classification counts old paths: renames (`git diff --no-renames`, numstat `=>` notation,
  unified-diff `rename from`) and deletions include the original path, so moving or deleting code
  can never read as a docs-only change. Local classification includes untracked files; the
  unified-diff parser sees empty added/deleted files and no longer mistakes a removed `-- ` line
  for a file header; edits to reviewer prompts (`**/lenses/**`) and agent
  instructions (`CLAUDE.md`, `AGENTS.md`, `.claude/`, `.cursor/`) are scoped, never light. `init` adds `.greenbar/` to
  `.gitignore`.
- `greenbar draft` reads the goal from a `## Goal` (or `## Objective` / `## Problem`) section when
  the PRD has no labelled goal line.
- Durable gate history for `accountability`: `greenbar gate --notes` writes the event as a git note
  (`refs/notes/greenbar`); `report`/`accountability` read notes plus the local file (`--no-notes`
  to skip). `GREENBAR_COMMIT` overrides HEAD (PR runs use the head SHA, not GitHub's synthetic
  merge commit). The PR workflow's `record` job notes the merged PR's check result on the landed
  commit. The MCP `greenbar_gate` tool now records history too.

### Added
- `greenbar mcp` — a minimal MCP (Model Context Protocol) server over stdio, in pure stdlib
  (newline-delimited JSON-RPC 2.0, no SDK dependency), exposing `greenbar_orient`, `greenbar_lint`,
  `greenbar_classify`, `greenbar_draft`, `greenbar_gate`, and `greenbar_report` as tools any coding
  agent (Claude Code, Cursor) can call mid-task. Handles initialize / tools/list / tools/call /
  ping; tool errors, unknown tools/methods, and malformed lines all degrade in-band without
  crashing the loop.

### Changed
- Packaging: first PyPI-ready release. Version is now single-sourced from `greenbar.__version__`
  (pyproject reads it dynamically); `requires-python` is honestly `>=3.10` (the code uses PEP 604
  `X | Y` in evaluated signatures — 3.9 is EOL and now refused by metadata, not silently broken);
  added PyPI classifiers + project URLs. The release workflow tests on 3.10–3.13, `twine check`s
  the artifacts, guards tag==version, and publishes via OIDC trusted publishing (no stored token).

## [0.9.0] - 2026-08-03
### Added
- `greenbar render` — turn the latest gate event + review record(s) into a Markdown PR summary
  (gate table, review verdicts + findings, rubber-stamp flag) with a stable marker for one-comment
  upsert. CLI renders; the Action posts.
- A shipped GitHub workflow (`templates/github/greenbar-pr.yml`) that runs `greenbar gate --auto` as a
  required check (blocks merge) and upserts a single PR comment using the repo's GITHUB_TOKEN — a
  PR-native experience with no hosted service.

## [0.8.0] - 2026-08-03
### Added
- `greenbar accountability` — the loop's payoff, measured: `gate` now stamps the commit SHA on its
  history event, and this command reads git for reverts, links each to the reverted commit, and
  reports the **defect-escape rate** (gate-passed changes later reverted / all gated changes) plus
  mean time-to-revert. `--incidents <sha-file>` folds in incident-linked commits. Reverts are an
  honestly-labelled proxy; commits Greenbar never gated are reported as 'ungoverned', not escapes.

## [0.7.0] - 2026-08-03
### Added
- `greenbar draft <prd>` — scaffold a lint-clean contract from a PRD: pulls goal, non-goals, and
  acceptance stubs from the text and fills the quality axes from the project catalog. Works with no
  LLM by default; `--with "<cmd>"` drafts via any model CLI (provider-agnostic), falling back to the
  deterministic draft on failure.
- `greenbar init --preset python|node|go|rust` — write a stack-gated greenbar.yaml (ruff/pytest,
  eslint/tsc, go vet/test, cargo clippy/test) in one command; unknown preset falls back to generic.

## [0.6.0] - 2026-08-03
### Added
- Architecture **design-lens pack**: five discipline lenses (abstraction-contracts, distributed-
  invariants, systems-simplicity, evolutionary-design, domain-model) shipped as rubric files and
  copied by `greenbar init` into `lenses/`. Named by discipline, not by person.
- Lenses gain `persona_file` (load a rubric from disk) and `group` (`greenbar review --group design`
  runs only that set) — enabling a design review distinct from the code review.
- A `design` tier and a deterministic `builtin: adr` gate (an ADR must exist and, when configured,
  reference the design's contract id). TLA+/model-checkers are a documented `run:` recipe, not core.

## [0.5.0] - 2026-08-02
### Added
- Polyglot `greenbar orient` via an optional tree-sitter extractor (`pip install greenbar[treesitter]`)
  covering JS/TS, Go, Rust, Java, C/C++, Kotlin, Swift, Ruby, C#, and more. `build_graph` dispatches each
  file to the right extractor by extension; core stays dependency-light and orient runs Python-only when
  the extra is absent. Unsupported files / parse failures are skipped, not fatal.

## [0.4.0] - 2026-08-02
### Added
- `greenbar orient` — a token-bounded, rank-ordered code map for agent orientation. Builds a
  symbol graph (Python via the stdlib `ast` module; pluggable extractor for other languages),
  ranks with a personalized PageRank (biased toward the changed files when `--diff` is given),
  and renders the top symbols within a token budget. Broken source files are skipped, not fatal.

## [0.3.0] - 2026-08-02
### Added
- `greenbar classify` — infer a change's tier from its diff (path globs + file/line thresholds,
  first-match-wins; a rule with no conditions never matches).
- `greenbar gate --auto` — classify the diff, then run the inferred tier (rigor scales to blast
  radius automatically).
- `greenbar report` — aggregate the run history (`.greenbar/history.jsonl`, appended by every
  `gate`/`review`): gate pass-rate + failures-by-gate, review verdict distribution, rubber-stamp
  rate, and a `signals` section. Defect-escape is an honestly-labelled proxy.

## [0.2.0] - 2026-07-28
### Added
- `greenbar review` — a provider-agnostic, cross-model review-panel runner. Each lens is a shell
  command (LLM CLI or a deterministic analyzer); lenses run in parallel and their verdicts +
  findings are written to `.greenbar/review-record.json`.
- `builtin: review` gate — requires a **fresh** (matches the current contract), non-**BLOCK**
  review record; fail-closed (an unparseable/timed-out lens is `ERROR`, never a silent SIGN);
  computes an all-SIGN/zero-findings rubber-stamp signal.

## [0.1.0] - 2026-07-28
### Added
- Machine-checked contract linter (`greenbar lint`): binary acceptance criteria and a quality-axis
  block where every asserted axis must carry a behavioral must-have KPI (or be deferred / n_a with
  a sign-off).
- Tier/gate ladder (`greenbar gate <tier>`): three gate kinds — `builtin: contract`, `run: <cmd>`,
  `requires_file: <path>` — exiting non-zero when a required gate fails.
- `greenbar init` scaffolding, a reusable GitHub Action, and adapters for Claude Code + Cursor.
- Dogfooding: the repo carries its own `greenbar.yaml` + `contracts/CONTRACT.md` and gates itself.

[Unreleased]: https://github.com/subirroy71/greenbar/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/subirroy71/greenbar/releases/tag/v0.10.0
