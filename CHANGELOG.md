# Changelog

All notable changes to Trellis are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Trellis adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-08-03
First tagged and PyPI-published release (v0.1–v0.9 were developed on `main` but never tagged).

### Added
- `trellis mcp` — a minimal MCP (Model Context Protocol) server over stdio, in pure stdlib
  (newline-delimited JSON-RPC 2.0, no SDK dependency), exposing `trellis_orient`, `trellis_lint`,
  `trellis_classify`, `trellis_draft`, `trellis_gate`, and `trellis_report` as tools any coding
  agent (Claude Code, Cursor) can call mid-task. Handles initialize / tools/list / tools/call /
  ping; tool errors, unknown tools/methods, and malformed lines all degrade in-band without
  crashing the loop.

### Changed
- Packaging: first PyPI-ready release. Version is now single-sourced from `trellis.__version__`
  (pyproject reads it dynamically); `requires-python` is honestly `>=3.10` (the code uses PEP 604
  `X | Y` in evaluated signatures — 3.9 is EOL and now refused by metadata, not silently broken);
  added PyPI classifiers + project URLs. The release workflow tests on 3.10–3.13, `twine check`s
  the artifacts, guards tag==version, and publishes via OIDC trusted publishing (no stored token).

## [0.9.0] - 2026-08-03
### Added
- `trellis render` — turn the latest gate event + review record(s) into a Markdown PR summary
  (gate table, review verdicts + findings, rubber-stamp flag) with a stable marker for one-comment
  upsert. CLI renders; the Action posts.
- A shipped GitHub workflow (`templates/github/trellis-pr.yml`) that runs `trellis gate --auto` as a
  required check (blocks merge) and upserts a single PR comment using the repo's GITHUB_TOKEN — a
  PR-native experience with no hosted service.

## [0.8.0] - 2026-08-03
### Added
- `trellis accountability` — the loop's payoff, measured: `gate` now stamps the commit SHA on its
  history event, and this command reads git for reverts, links each to the reverted commit, and
  reports the **defect-escape rate** (gate-passed changes later reverted / all gated changes) plus
  mean time-to-revert. `--incidents <sha-file>` folds in incident-linked commits. Reverts are an
  honestly-labelled proxy; commits Trellis never gated are reported as 'ungoverned', not escapes.

## [0.7.0] - 2026-08-03
### Added
- `trellis draft <prd>` — scaffold a lint-clean contract from a PRD: pulls goal, non-goals, and
  acceptance stubs from the text and fills the quality axes from the project catalog. Works with no
  LLM by default; `--with "<cmd>"` drafts via any model CLI (provider-agnostic), falling back to the
  deterministic draft on failure.
- `trellis init --preset python|node|go|rust` — write a stack-gated trellis.yaml (ruff/pytest,
  eslint/tsc, go vet/test, cargo clippy/test) in one command; unknown preset falls back to generic.

## [0.6.0] - 2026-08-03
### Added
- Architecture **design-lens pack**: five discipline lenses (abstraction-contracts, distributed-
  invariants, systems-simplicity, evolutionary-design, domain-model) shipped as rubric files and
  copied by `trellis init` into `lenses/`. Named by discipline, not by person.
- Lenses gain `persona_file` (load a rubric from disk) and `group` (`trellis review --group design`
  runs only that set) — enabling a design review distinct from the code review.
- A `design` tier and a deterministic `builtin: adr` gate (an ADR must exist and, when configured,
  reference the design's contract id). TLA+/model-checkers are a documented `run:` recipe, not core.

## [0.5.0] - 2026-08-02
### Added
- Polyglot `trellis orient` via an optional tree-sitter extractor (`pip install trellis-loop[treesitter]`)
  covering JS/TS, Go, Rust, Java, C/C++, Kotlin, Swift, Ruby, C#, and more. `build_graph` dispatches each
  file to the right extractor by extension; core stays dependency-light and orient runs Python-only when
  the extra is absent. Unsupported files / parse failures are skipped, not fatal.

## [0.4.0] - 2026-08-02
### Added
- `trellis orient` — a token-bounded, rank-ordered code map for agent orientation. Builds a
  symbol graph (Python via the stdlib `ast` module; pluggable extractor for other languages),
  ranks with a personalized PageRank (biased toward the changed files when `--diff` is given),
  and renders the top symbols within a token budget. Broken source files are skipped, not fatal.

## [0.3.0] - 2026-08-02
### Added
- `trellis classify` — infer a change's tier from its diff (path globs + file/line thresholds,
  first-match-wins; a rule with no conditions never matches).
- `trellis gate --auto` — classify the diff, then run the inferred tier (rigor scales to blast
  radius automatically).
- `trellis report` — aggregate the run history (`.trellis/history.jsonl`, appended by every
  `gate`/`review`): gate pass-rate + failures-by-gate, review verdict distribution, rubber-stamp
  rate, and a `signals` section. Defect-escape is an honestly-labelled proxy.

## [0.2.0] - 2026-07-28
### Added
- `trellis review` — a provider-agnostic, cross-model review-panel runner. Each lens is a shell
  command (LLM CLI or a deterministic analyzer); lenses run in parallel and their verdicts +
  findings are written to `.trellis/review-record.json`.
- `builtin: review` gate — requires a **fresh** (matches the current contract), non-**BLOCK**
  review record; fail-closed (an unparseable/timed-out lens is `ERROR`, never a silent SIGN);
  computes an all-SIGN/zero-findings rubber-stamp signal.

## [0.1.0] - 2026-07-28
### Added
- Machine-checked contract linter (`trellis lint`): binary acceptance criteria and a quality-axis
  block where every asserted axis must carry a behavioral must-have KPI (or be deferred / n_a with
  a sign-off).
- Tier/gate ladder (`trellis gate <tier>`): three gate kinds — `builtin: contract`, `run: <cmd>`,
  `requires_file: <path>` — exiting non-zero when a required gate fails.
- `trellis init` scaffolding, a reusable GitHub Action, and adapters for Claude Code + Cursor.
- Dogfooding: the repo carries its own `trellis.yaml` + `contracts/CONTRACT.md` and gates itself.

[Unreleased]: https://github.com/subirroy71/trellis/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/subirroy71/trellis/releases/tag/v0.10.0
