# Trellis

**Contract-first, gate-enforced development — turn your best-practices into CI gates, not prose an operator chooses to follow.**

Most "AI dev workflows" (and most human ones) *generate* rigor — a nice spec, a review pass, a Definition of Done — but they don't *guarantee* it. The standards live in a doc; whether they're followed depends on discipline. Trellis makes the rigor **mechanical**: a change declares a machine-checked **contract**, and a **tier of gates** must be green before it can merge. Skipping the process becomes a failing build, not a judgment call.

> Trellis is a distilled, tool-agnostic, *enforced* generalization of a governed loop we ran in production — the practices are old (spec-driven dev, design-by-contract, TDD, quality gates, adversarial review); the contribution is making them **fail the build when absent.**

---

## The idea in 30 seconds

1. **Contract** — every non-trivial change gets a `CONTRACT.md`: a machine-checked goal, *binary* acceptance criteria, and **quality axes with behavioral KPIs**. `trellis lint` validates it.
2. **Tiers** — a change declares its blast radius (`trivial` / `scoped` / `critical`). The tier fixes which gates are required, so rigor scales to impact instead of being all-or-nothing.
3. **Gates** — `trellis gate <tier>` runs the required checks (the contract linter, your lint/types/tests/coverage, a required review record, …) and **exits non-zero if any fail.** Wire it into CI + branch protection and the process is enforced.

The signature rule: **an asserted quality axis must carry a behavioral must-have KPI, or be explicitly deferred / marked n/a with a sign-off.** "We'll handle accuracy" is not a plan; a linter now says so.

## Quickstart

```bash
pipx install trellis-loop          # or: pip install trellis-loop
cd your-repo
trellis init                       # writes trellis.yaml + contracts/CONTRACT.example.md
$EDITOR contracts/CONTRACT.example.md
trellis lint contracts/CONTRACT.example.md
trellis gate scoped --contract contracts/CONTRACT.example.md
```

In CI (a change cannot merge unless its tier is green):

```yaml
# .github/workflows/trellis.yml
- uses: your-org/trellis-action@v1
  with:
    tier: scoped
    contract: contracts/CONTRACT.md
```

## What a contract looks like

```yaml
---
id: add-rate-limit
goal: "Cap /login to 5/min/IP · measurable: 6th request in a window → 429 · constraint: no false 429s for distinct IPs."
tier: scoped
non_goals: ["global rate limiting", "per-user quotas"]
acceptance:
  - { id: A1, must: "6th request from one IP in 60s returns 429" }
  - { id: A2, must: "distinct IPs are never throttled by each other" }
quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: deferred, deferred_to: "load-test issue #88" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1+A2 pass" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "0 false 429s across 1k distinct-IP requests" }
hitl: ["merge to main"]
---
# Context, method, and the DO-NOT list live here (prose — read by the reviewer, not linted).
```

`trellis lint` fails this if, say, `reasonableness@C` is `asserted` but no `must_have` KPI references it, or a profile axis is left undeclared, or a `deferred` axis names no target.

## Configure it for your stack — `trellis.yaml`

```yaml
axes:                       # the quality-axis catalog per profile (yours to define)
  C: [correctness, reasonableness, performance]
  D: [provenance, consistency, correctness, freshness]
tiers:                      # blast-radius ladder
  trivial:  { gates: [contract] }
  scoped:   { gates: [contract, lint, test] }
  critical: { gates: [contract, lint, test, coverage, review-record] }
gates:
  contract:      { builtin: contract }
  lint:          { run: "ruff check ." }        # swap for your linter
  test:          { run: "pytest -q" }
  coverage:      { run: "pytest -q --cov --cov-fail-under=70" }
  review-record: { requires_file: ".trellis/review-record.json" }
```

Gate kinds: `builtin: contract` (the contract validator), `builtin: review` (a fresh, non-BLOCK review record must exist), `run:` (any command that exits 0 on pass), `requires_file:` (an artifact must exist).

## Review panel — `trellis review`

Turn "run a multi-persona review by hand" into a reproducible, gate-able artifact. Each **lens** is a shell command — Trellis calls no LLM directly, so it's provider-agnostic and **cross-model falls out of pointing different lenses at different model CLIs**:

```yaml
review: { parallelism: 4, timeout_s: 300 }
lenses:
  - name: static                                   # a deterministic lens — verdict from exit code
    command: "ruff check . && mypy src"
    deterministic: true
  - name: correctness                              # an LLM lens on model A
    command: "claude -p --model claude-sonnet-4"
    persona: "Rigorous correctness reviewer. Trace every changed path."
  - name: security                                 # an LLM lens on model B (cross-model)
    command: "llm -m gpt-4o"
    persona: "Security auditor. Hunt auth/secret/injection."
```

```bash
trellis review --contract contracts/CONTRACT.md   # runs lenses in parallel → .trellis/review-record.json
trellis gate critical --contract contracts/CONTRACT.md   # the `review` gate consumes it
```

Each lens gets the persona + contract + diff on stdin and ends with `{"verdict":"SIGN|SIGN_WITH_CHANGE|BLOCK","findings":[...]}`. The record is **fail-closed** (a lens that times out or emits no parseable verdict is `ERROR`, never a silent SIGN), carries a **context hash** (prove which tree was reviewed), and computes a **rubber-stamp signal** (all-SIGN with zero findings). The `review` gate fails if the record is **missing, stale** (the contract changed since the review), or **BLOCKED** — so a review of an old version can't wave a change through.

## Auto-tiering & metrics — `trellis classify` / `trellis report`

**Stop deciding the tier by hand.** Declare rules once; Trellis infers a change's blast radius from its diff (first match wins):

```yaml
classify:
  default: scoped
  rules:
    - { tier: critical, any_path: ["**/migrations/**", "**/auth/**", "**/*secret*"] }
    - { tier: critical, min_files: 30 }
    - { tier: trivial,  only_paths: ["**/*.md", "docs/**"] }
    - { tier: trivial,  max_files: 1, max_lines: 10 }
```

```bash
trellis classify                 # → tier: critical  (rule[0] matched {any_path: [**/migrations/**]})
trellis gate --auto --contract contracts/CONTRACT.md   # classify, then run the inferred tier
```

So a docs typo runs the `trivial` gates and a migration change runs `critical` — rigor scales to impact automatically.

**Measure whether the loop is paying.** Every `gate`/`review` appends to `.trellis/history.jsonl`; `trellis report` aggregates it:

```
$ trellis report
gate runs:        42   pass rate: 88%   failures/gate: {test: 4, contract: 1}
review runs:      18   verdicts: {PASS: 11, CHANGES: 6, BLOCKED: 1}
  catch-rate*:    39%   rubber-stamp: 6%   avg findings: 1.7
signals:
  ⚠ over half of reviews were all-SIGN with zero findings — possible rubber-stamping
```

Proxies (defect-escape) are labelled as proxies — no overclaiming.

## How this compares

| | Advisory doc / checklist | AI reviewer bot (post-PR) | **Trellis** |
|---|---|---|---|
| Enforced? | No — honor system | Comments, rarely blocking | **Yes — gate exits non-zero** |
| Contract validated by | a human reading it | n/a | **a linter** |
| Rigor scales to blast radius | no | no | **tiers** |
| Tool-locked | — | usually SaaS | **tool-agnostic (CLI + Action)** |
| The "did we declare how we'd verify quality?" check | tribal | no | **a build failure** |

Trellis isn't a code reviewer — it's the layer that guarantees the reviewer, the tests, and the contract *actually ran*. Pair it with your reviewer bot / test suite; it makes them non-skippable.

## Roadmap

- **v0.1:** contract schema + linter, tier/gate ladder, CLI, GitHub Action, adapters. ✅
- **v0.2:** `trellis review` — pluggable, cross-model, deterministic-plus-LLM review panel producing the record the `review` gate enforces (fail-closed, freshness-pinned, rubber-stamp signal). ✅
- **v0.3:** `trellis classify` / `gate --auto` (auto blast-radius tiering from the diff) + `trellis report` (gate/review history metrics with honest proxies + rubber-stamp signal). ✅
- **v0.4 (ideas):** a mutation-testing gate helper, direct-API lens providers (optional extra), a defect-escape metric wired to prod, and per-repo policy presets.

## Adapters

Wire the loop into your agentic coding tool so the agent authors a contract and runs the gates before pushing:
- `adapters/claude-code/` — a Claude Code skill + `CLAUDE.md` snippet
- `adapters/cursor/` — Cursor rules

## License

Apache-2.0. Contributions welcome — see `CONTRIBUTING.md`. Trellis dogfoods itself: this repo has its own `trellis.yaml` + `contracts/CONTRACT.md`, and CI runs `trellis gate scoped` on every PR.
