# Changelog

All notable changes to Trellis are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and Trellis adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/subirroy71/trellis/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/subirroy71/trellis/releases/tag/v0.3.0
[0.2.0]: https://github.com/subirroy71/trellis/releases/tag/v0.2.0
[0.1.0]: https://github.com/subirroy71/trellis/releases/tag/v0.1.0
