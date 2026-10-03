"""Gate ladder — the three gate kinds + tier aggregation, against a temp project."""

import pytest

from trellis.config import load_config
from trellis.gates import run_gate, run_tier

_CONFIG = """
axes:
  C: [correctness]
tiers:
  ok:   { gates: [truth] }
  bad:  { gates: [falsehood] }
  file: { gates: [needs_file] }
gates:
  truth:     { run: "true" }
  falsehood: { run: "false" }
  needs_file: { requires_file: "PRESENT.txt" }
  contract:  { builtin: contract }
"""

_GOOD_CONTRACT = """---
id: x
goal: g
tier: ok
non_goals: [n]
acceptance: [{id: A1, must: verifiable}]
quality_axes:
  profiles: [C]
  axes: { correctness@C: { state: asserted } }
  kpis: [{id: K1, axis: correctness, profile: C, must_have: true, target: t}]
---
body
"""


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "trellis.yaml").write_text(_CONFIG)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_run_gate_shell_pass_and_fail(project):
    cfg = load_config()
    assert run_gate("truth", cfg.gates["truth"], cfg, None).ok is True
    assert run_gate("falsehood", cfg.gates["falsehood"], cfg, None).ok is False


def test_requires_file_gate(project):
    cfg = load_config()
    assert run_gate("needs_file", cfg.gates["needs_file"], cfg, None).ok is False
    (project / "PRESENT.txt").write_text("x")
    assert run_gate("needs_file", cfg.gates["needs_file"], cfg, None).ok is True


def test_builtin_contract_gate(project):
    c = project / "CONTRACT.md"
    c.write_text(_GOOD_CONTRACT)
    cfg = load_config()
    assert run_gate("contract", cfg.gates["contract"], cfg, str(c)).ok is True
    # a contract with an asserted axis but no KPI fails the gate
    c.write_text(_GOOD_CONTRACT.replace("kpis: [{id: K1, axis: correctness, profile: C, must_have: true, target: t}]", "kpis: []"))
    r = run_gate("contract", cfg.gates["contract"], cfg, str(c))
    assert r.ok is False and "C008" in r.detail


def test_run_tier_aggregates(project):
    cfg = load_config()
    assert all(r.ok for r in run_tier("ok", cfg))
    assert any(not r.ok for r in run_tier("bad", cfg))


def test_unknown_tier_raises(project):
    with pytest.raises(KeyError):
        run_tier("nope", load_config())
