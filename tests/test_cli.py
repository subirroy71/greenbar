"""End-to-end CLI: init scaffolds, lint/gate return the exit codes CI blocks on."""
from pathlib import Path

import pytest

from trellis.cli import main


def test_init_then_lint_then_gate(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # init scaffolds a config + example contract
    assert main(["init"]) == 0
    assert (tmp_path / "trellis.yaml").exists()
    contract = tmp_path / "contracts" / "CONTRACT.example.md"
    assert contract.exists()

    # the shipped example contract is valid → lint exits 0
    assert main(["lint", str(contract)]) == 0

    # gate 'trivial' only requires the contract gate → passes with a valid contract
    assert main(["gate", "trivial", "--contract", str(contract)]) == 0


def test_lint_fails_on_bad_contract(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    bad = tmp_path / "contracts" / "bad.md"
    bad.write_text(
        "---\n"
        "id: b\ngoal: g\ntier: scoped\n"
        "acceptance: [{id: A1, must: x}]\n"
        "quality_axes:\n"
        "  profiles: [C]\n"
        "  axes: { correctness@C: { state: asserted } }\n"  # asserted, no KPI, and 2 axes unaccounted
        "  kpis: []\n"
        "---\nbody\n"
    )
    assert main(["lint", str(bad)]) == 1  # non-zero → CI blocks


def test_gate_blocks_when_review_record_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["init"])
    contract = tmp_path / "contracts" / "CONTRACT.example.md"
    # 'critical' requires a review-record artifact that doesn't exist yet → gate fails (exit 1)
    # (only assert the contract+record interplay; lint/test gates may or may not have tooling here)
    from trellis.config import load_config
    from trellis.gates import run_gate
    cfg = load_config()
    r = run_gate("review-record", cfg.gates["review-record"], cfg, str(contract))
    assert r.ok is False
    Path(".trellis").mkdir(exist_ok=True)
    Path(".trellis/review-record.json").write_text("{}")
    r2 = run_gate("review-record", cfg.gates["review-record"], cfg, str(contract))
    assert r2.ok is True
