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

## Quickstart (≈5 minutes)

```bash
pipx install trellis-loop                 # or: pip install trellis-loop
cd your-repo
trellis init --preset python              # gated for your stack in one command (python|node|go|rust)
trellis draft docs/PRD.md                 # scaffold a lint-clean contract FROM your PRD (no blank page)
$EDITOR contracts/<id>.md                 # fill the TODO targets
trellis lint contracts/<id>.md
trellis gate --auto --contract contracts/<id>.md   # classify the diff, run the right tier
```

**`trellis draft`** turns a PRD/issue into a starting contract — pulling the goal, non-goals, and acceptance stubs out of the text and filling the quality axes from your project catalog, so you edit instead of stare at a blank frontmatter. It works with **no LLM** by default; `trellis draft PRD.md --with "claude -p"` uses a model CLI (provider-agnostic), falling back to the deterministic draft if that fails.

**`trellis init --preset <stack>`** writes a `trellis.yaml` with your stack's gate commands (ruff/pytest, eslint/tsc, go vet/test, cargo clippy/test) + the tier ladder + the design-lens pack — no hand-written YAML to start.

In CI (a change cannot merge unless its tier is green):

```yaml
# .github/workflows/trellis.yml
- uses: your-org/trellis-action@v1
  with:
    tier: scoped
    contract: contracts/CONTRACT.md
```

### PR-native — a required check + one comment (no hosted service)

Drop in the shipped workflow (`src/trellis/templates/github/trellis-pr.yml` → `.github/workflows/`). On every PR it runs `trellis gate --auto` as a **required check that blocks merge**, then upserts **one** comment (never spams) with the gate table + review findings — using only the repo's `GITHUB_TOKEN`:

```markdown
## 🌿 Trellis
**Gate `critical`: ✅ pass**
| gate | result |  |
|---|---|
| `contract` | ✅ | `test` ✅ · `coverage` ✅ · `review` ✅ |
**Code review: 🔸 CHANGES** · 3 lenses · 2 findings
- 🔸 _security_ — rate limit is per-username; also consider per-IP
- 🔸 _abstraction_ — the Store interface leaks ordering
```

`trellis render` produces that Markdown from the local artifacts (CLI renders; the Action posts) — so a hosted GitHub App is unnecessary.

### Agent-native — an MCP server (no SDK dependency)

`trellis mcp` runs an [MCP](https://modelcontextprotocol.io) server over stdio, so any coding agent can call Trellis as first-class tools mid-task — `trellis_orient` (map the code), `trellis_lint` (check a contract), `trellis_classify` (tier a change), `trellis_draft` (contract from a PRD), `trellis_gate`, `trellis_report`. It's implemented in pure stdlib (newline-delimited JSON-RPC 2.0) — no MCP SDK in core.

```bash
# Claude Code
claude mcp add trellis -- trellis mcp
```

```jsonc
// Cursor — .cursor/mcp.json  (or any MCP client)
{ "mcpServers": { "trellis": { "command": "trellis", "args": ["mcp"] } } }
```

Now the agent orients, drafts, and gates through the same governed loop a human does — the framework travels into the agent instead of sitting beside it.

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

## Design-phase review — an architecture lens pack

Move the multi-lens review *earlier* — onto the design doc, before code. Trellis ships five **discipline** lenses (distilled from durable schools of software architecture — named by discipline, **not** impersonating people):

| Lens | The question it forces |
|---|---|
| `abstraction` | Do the abstractions hold? Are contracts substitutable? Where does it leak? (Liskov / DbC) |
| `invariants` | What safety/liveness invariants must hold under concurrency + failure — and can you prove them? (Lamport) |
| `simplicity` | Least mechanism; do one thing well; is the common case simple + fast? (Lampson's *Hints*) |
| `evolution` | YAGNI; reversibility; testable seams; the refactoring path if we're wrong (Fowler) |
| `domain` | Does the model match the domain? Bounded contexts, aggregates, ubiquitous language? (Evans/DDD) |

`trellis init` drops the rubrics into `lenses/`. Wire each to a model CLI (cross-model encouraged), then:

```bash
trellis review --group design --out .trellis/design-review.json --contract contracts/<id>.md
trellis gate design --contract contracts/<id>.md      # gates: [contract, adr, design-review]
```

The `design` tier adds a deterministic **`builtin: adr` gate** — an Architecture Decision Record must exist *and reference this design* — so every design-tier change leaves a decision trail. And where a school has a **formal tool**, wire the tool, not a prompt: a `deterministic` lens that runs **TLA+** (`tlc spec/Design.tla`) is a truer "invariants" check than any persona.

> The honest framing: the lenses give you the *breadth* of those schools' thinking; the ADR + TLA+ gates give *depth* where it exists; cross-model keeps it from being a mirror that agrees with itself.

## Orient before you edit — `trellis orient`

Instead of reading 15k tokens of files to find where to look, build a symbol graph of the repo and emit a **token-bounded, rank-ordered code map** — and, focused on a diff, "what does *this* change touch and connect to." Dependency-light: Python via the stdlib `ast` module (no deps); other languages plug in via an optional extractor.

```bash
trellis orient --budget 1200                 # a repo map: top symbols by centrality, within a token budget
trellis orient --diff-base main              # FOCUSED: bias the map toward the changed files (personalized PageRank)
trellis orient --json                        # machine-readable, for feeding an agent
```
```
# orientation for 1 changed file(s) · 143 symbols in graph
src/trellis/orient.py
  src/trellis/orient.py:130  def build_graph(root, extractor=None, exclude=(...))
  src/trellis/orient.py:143  def pagerank(g, personalization=None, damping=0.85, iters=30)
  ...
```

**Python works with zero deps** (stdlib `ast`). For **polyglot** reach (JS/TS, Go, Rust, Java, C/C++, Kotlin, Swift, Ruby, C#, …), install the optional extra:

```bash
pip install "trellis-loop[treesitter]"       # adds a tree-sitter extractor; orient goes multi-language
```

Core stays dependency-light — without the extra, `orient` runs Python-only with no error; with it, `build_graph` dispatches each file to the right extractor by extension.

It's an *approximate* map (name-based edges, like a repo map) — an advisory read-replica of the code, to be verified against the source. That's the same discipline a code knowledge graph uses; Trellis just makes it a one-command orientation step.

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
- **v0.4:** `trellis orient` — a token-bounded, diff-focusable code map (stdlib-`ast` symbol graph + personalized PageRank; pluggable extractor for other languages). ✅
- **v0.5:** polyglot `orient` — an optional `tree-sitter` extractor (`[treesitter]` extra) covering JS/TS, Go, Rust, Java, C/C++, Kotlin, Swift, Ruby, C#, …; core stays dependency-light. ✅
- **v0.6:** architecture design-lens pack — 5 discipline lenses (`persona_file` + `group`), a `design` tier, and a deterministic `builtin: adr` gate; design review runs before code. ✅
- **v0.7:** onboarding — `trellis draft` (contract from a PRD, deterministic or `--with` a model CLI) + `trellis init --preset python|node|go|rust` (stack-gated in one command). ✅
- **v0.8:** `trellis accountability` — defect-escape rate (gate-passed changes later reverted), the "does the loop pay?" metric, honest by construction. ✅
- **v0.9:** PR-native — `trellis render` + a shipped GitHub workflow: a required gate check that blocks merge and one upserted PR comment (gate table + review findings), no hosted service. ✅
- **v0.10:** agent-native — `trellis mcp`, a pure-stdlib MCP server exposing orient/lint/classify/draft/gate/report as tools any coding agent (Claude Code, Cursor) can call. ✅
- **v0.11 (ideas):** shareable policy packs (`soc2`, `fintech`, `oss-maintainer`).

## Adapters

Wire the loop into your agentic coding tool so the agent authors a contract and runs the gates before pushing:
- `adapters/claude-code/` — a Claude Code skill + `CLAUDE.md` snippet
- `adapters/cursor/` — Cursor rules

## License

Apache-2.0. Contributions welcome — see `CONTRIBUTING.md`. Trellis dogfoods itself: this repo has its own `trellis.yaml` + `contracts/CONTRACT.md`, and CI runs `trellis gate scoped` on every PR.
