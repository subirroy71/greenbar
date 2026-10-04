---
id: greenbar-v0.10.1-release
goal: "Ship the post-launch fixes to PyPI as 0.10.1 · measurable: the tag builds, passes the 3.10–3.13 matrix and publishes, and `pip install greenbar==0.10.1` reports 0.10.1 · constraint: no behaviour change beyond what the CHANGELOG lists."
tier: scoped

non_goals:
  - "new features — this release only carries the readable-comment and record-job fixes"

acceptance:
  - { id: A1, must: "`greenbar.__version__` is 0.10.1 and the release workflow's tag-equals-version check passes for v0.10.1" }
  - { id: A2, must: "CHANGELOG has a dated [0.10.1] section holding the two fixes, an empty [Unreleased], and compare links for both" }
  - { id: A3, must: "a clean install of greenbar 0.10.1 from PyPI runs and renders '1 lens' in a review summary" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-10-03 — version metadata only" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "release workflow green end to end for v0.10.1 (A1); PyPI serves 0.10.1 (A3)" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "the full test suite passes unchanged at the release commit" }

hitl:
  - "merge to main"
  - "publish to PyPI (push the v0.10.1 tag)"
---

# Release 0.10.1

Carries the two fixes merged after 0.10.0 (#2 readable PR comments, #4 record-job resilience) to
PyPI, so design partners — starting with internship-watch — install the current behaviour.
