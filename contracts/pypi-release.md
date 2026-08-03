---
id: trellis-v0.10-pypi-release
goal: "Make trellis-loop installable from PyPI: reconcile the version to a single source, tell the truth about supported Python, and gate the release on a verified build + trusted-publishing workflow · measurable: `python -m build` + `twine check` pass, the wheel installs and runs on a clean 3.10+ env, and requires-python refuses 3.9 · constraint: no stored PyPI token (OIDC trusted publishing); publish + go-public are HITL."
tier: scoped

non_goals:
  - "actually publishing to PyPI or flipping the repo public — both are HITL, parked for the maintainer"
  - "supporting Python 3.9 — it is EOL and the code uses PEP 604 `X | Y` in evaluated signatures; claim only what is tested"
  - "storing a PyPI API token — trusted publishing (OIDC) instead"

acceptance:
  - { id: A1, must: "the package version has a single source (`trellis.__version__`); pyproject reads it dynamically — no second literal to drift" }
  - { id: A2, must: "requires-python is >=3.10 (honest: the code breaks on 3.9) and the release CI runs the suite on 3.10–3.13" }
  - { id: A3, must: "`python -m build` produces an sdist+wheel stamped 0.10.0 and `twine check` passes both" }
  - { id: A4, must: "the wheel installs into a clean 3.10+ venv and `trellis` (CLI + `trellis mcp`) runs from bundled data; a 3.9 install is refused by metadata" }
  - { id: A5, must: "the release workflow publishes via OIDC trusted publishing (no token) and refuses a tag whose version != the package version" }

quality_axes:
  profiles: [C]
  axes:
    correctness@C:    { state: asserted }
    reasonableness@C: { state: asserted }
    performance@C:    { state: n_a, signoff: "author 2026-08-03 — packaging config has no runtime hot path" }
  kpis:
    - { id: K1, axis: correctness,    profile: C, must_have: true, target: "build + twine check pass; wheel imports version 0.10.0 on a clean 3.10+ env (A3, A4)" }
    - { id: K2, axis: reasonableness, profile: C, must_have: true, target: "requires-python matches what is actually tested; 3.9 is refused, not silently broken (A2, A4)" }

hitl:
  - "publish to PyPI (push the v0.10.0 tag / register the trusted publisher)"
  - "flip the repository public"
---

# Trellis v0.10 — PyPI release prep

**Why.** Nothing above the CLI is real to an outside user until they can `pip install trellis-loop`
and `claude mcp add trellis`. This makes the artifact real and honest — one version source, a
Python-support claim that is machine-verified, and a release path with no secret to leak.

**How.** `pyproject` version becomes `dynamic` off `trellis.__version__` (SSOT, CHOP §1);
`requires-python` drops to the truthful `>=3.10`; the release workflow tests the matrix, builds,
`twine check`s, guards tag==version, and publishes via OIDC trusted publishing.

**DO NOT.** Publish or go-public here (both HITL). Store a PyPI token. Claim a Python version the
suite does not run on.
