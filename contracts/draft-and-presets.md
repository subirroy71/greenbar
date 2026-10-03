---
id: greenbar-v0.7-draft-and-presets
goal: "Kill onboarding friction: `greenbar draft <prd>` scaffolds a lint-clean contract from a PRD (deterministic by default; LLM-assisted with --with), and `greenbar init --preset <stack>` fills gates for python/node/go/rust · measurable: draft of a PRD yields a contract that `greenbar lint` passes; init --preset writes stack-appropriate gates · constraint: draft works with NO LLM (dependency-light); the LLM path is provider-agnostic."
tier: scoped

non_goals:
  - "authoring a perfect contract — draft removes the blank page; the human fills the TODO targets and lints"
  - "bundling an LLM SDK — --with runs any shell command (claude/llm/aider/script), same as review lenses"
  - "auto-detecting the stack — the user picks --preset explicitly"

acceptance:
  - { id: A1, must: "`greenbar draft <prd>` (no LLM) writes a contract whose frontmatter `greenbar lint` passes" }
  - { id: A2, must: "draft pulls goal, non_goals, and acceptance stubs out of the PRD text (not just an empty shell)" }
  - { id: A3, must: "the drafted quality_axes cover every axis of the chosen profile (asserted + a placeholder must_have KPI)" }
  - { id: A4, must: "`greenbar draft --with <cmd>` pipes the PRD + schema to the command and writes its output; a failed/empty command falls back to the deterministic draft" }
  - { id: A5, must: "`greenbar init --preset python|node|go|rust` writes a greenbar.yaml with that stack's gate commands" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-03 — PRD parsing + template selection is not perf-sensitive" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "A1-A5 each covered by a passing test" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "a PRD with no recognizable sections still yields a valid (placeholder) contract; a missing preset falls back to the generic template — never a crash" }

hitl:
  - "publish to PyPI"
  - "merge to main"
---

# Greenbar v0.7 — `greenbar draft` + stack presets

**Why.** The contract is the main adoption friction — a blank frontmatter is where people bounce.
`draft` turns a PRD into a lint-clean starting contract (goal/non-goals/acceptance pulled from the
text, quality axes filled from the project catalog); the human refines the TODO targets. Presets
get a repo gated in one command instead of hand-writing YAML.

**Dependency-light + provider-agnostic.** Draft works with NO LLM by default (heuristic PRD
parsing). `--with "<cmd>"` optionally pipes the PRD + the schema to any model CLI and writes its
output, falling back to the deterministic draft if that fails — the same tool-agnostic pattern as
the review lenses.

**DO NOT.** Require an LLM for draft; bundle an SDK; crash on an unstructured PRD or an unknown
preset (fall back); emit a contract that fails `lint`.
