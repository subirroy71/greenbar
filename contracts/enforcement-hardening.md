---
id: trellis-v0.10-enforcement-hardening
goal: "Close the enforcement holes found in pre-release review so the cheapest path to a green build can no longer skip the rigor · measurable: each hole has a regression test that fails on the old behaviour and passes now · constraint: no new runtime dependency; existing valid contracts and configs keep working."
tier: scoped

non_goals:
  - "renaming the project or the `.trellis/` state directory — a maintainer decision, parked"
  - "a lightweight contract mode for trivial tiers — a policy design change, not a fix"
  - "agent-boundary hooks or Spec Kit / OpenSpec contract sources — roadmap features"

acceptance:
  - { id: A1, must: "`trellis lint` fails (C012) on any TODO/TBD/FIXME left in goal, non_goals, acceptance, axes or KPIs — an unfilled `trellis draft` contract no longer passes" }
  - { id: A2, must: "a contract whose tier is not defined in trellis.yaml fails lint and the contract gate (C013); a must_have KPI with no target fails (C014)" }
  - { id: A3, must: "`trellis lint` on a file without frontmatter exits 1 with a C000 finding, never a traceback" }
  - { id: A4, must: "the review gate fails as STALE when any tracked file changed since the review, and stays fresh when the same content is merely committed" }
  - { id: A5, must: "a review with zero lenses is NO_LENSES: `trellis review` exits 1 and the review gate fails" }
  - { id: A6, must: "a `run:` gate that exceeds its timeout (gate `timeout_s`, top-level `gate_timeout_s`, default 1800s) fails instead of hanging" }
  - { id: A7, must: "`trellis gate --notes` stores the result as a git note that `accountability` reads after the local history is gone; `TRELLIS_COMMIT` overrides HEAD; the MCP gate tool records history" }
  - { id: A8, must: "the shipped PR workflow never falls back to an arbitrary contract, gates with the base branch's trellis.yaml, and records the merged PR's check result on the landed commit" }
  - { id: A9, must: "no shipped preset lens ends in `|| true` (a lens that always signs off)" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-10-03 — the fingerprint is one `git add -u` on a copied index; gates are CLI-bound" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "every acceptance criterion A1–A7, A9 is covered by a passing test in tests/test_hardening.py or the existing suites" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "all contracts already in contracts/ still lint clean against trellis.yaml (no false positives)" }

hitl:
  - "merge to main"
  - "make the repository public and decide the name before publishing"
---

# Enforcement hardening (pre-release)

**Why.** A pre-release review found that Trellis enforced the *shape* of the process but not its
substance: a drafted contract full of `TODO`s linted clean, a review of old code satisfied the
review gate, a zero-lens review was a PASS, the PR workflow could bind an unrelated contract, and
a PR could edit the policy that judged it. The product's claim is that skipping the process is a
failing build; for agents, which take the cheapest green path, each hole made that claim false.

**Method.** One regression test per hole (`tests/test_hardening.py`), then the smallest fix that
makes it pass. Review freshness uses a content fingerprint (a git tree id built from a throwaway
copy of the index) so committing after a review keeps it fresh while any edit makes it stale.
Durable history uses git notes, because CI runners are ephemeral and PR runs see a synthetic
merge commit no revert will ever name.
