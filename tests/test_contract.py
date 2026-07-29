"""The contract validator is the crown jewel — the rule that an asserted axis needs a behavioral
KPI is the whole reason Trellis beats an advisory checklist. These tests pin every rule."""
import pytest

from trellis.contract import parse_contract, validate_contract, ContractError

# a project axis catalog: profile C has three axes
CATALOG = {"C": ["correctness", "reasonableness", "performance"], "D": ["provenance"]}


def _codes(findings, level="error"):
    return {f.code for f in findings if f.level == level}


def _valid_meta():
    return {
        "id": "x",
        "goal": "do the thing",
        "tier": "scoped",
        "non_goals": ["not that"],
        "acceptance": [{"id": "A1", "must": "it is true or false"}],
        "quality_axes": {
            "profiles": ["C"],
            "axes": {
                "correctness@C": {"state": "asserted"},
                "reasonableness@C": {"state": "asserted"},
                "performance@C": {"state": "deferred", "deferred_to": "perf-harness"},
            },
            "kpis": [
                {"id": "K1", "axis": "correctness", "profile": "C", "must_have": True, "target": "0 fails"},
                {"id": "K2", "axis": "reasonableness", "profile": "C", "must_have": True, "target": "no degenerate"},
            ],
        },
        "hitl": ["merge to main"],
    }


def test_valid_contract_has_no_errors():
    assert _codes(validate_contract(_valid_meta(), CATALOG)) == set()


def test_missing_required_fields():
    findings = validate_contract({"id": "x"}, CATALOG)
    assert "C001" in _codes(findings)  # missing goal/tier/acceptance/quality_axes


def test_asserted_axis_without_musthave_kpi_is_an_error():
    """The signature catch: an axis asserted in name only (no behavioral KPI) fails the build."""
    m = _valid_meta()
    m["quality_axes"]["kpis"] = [k for k in m["quality_axes"]["kpis"] if k["axis"] != "reasonableness"]
    assert "C008" in _codes(validate_contract(m, CATALOG))


def test_unaccounted_profile_axis_is_an_error():
    m = _valid_meta()
    del m["quality_axes"]["axes"]["performance@C"]  # profile C axis left undeclared
    assert "C006" in _codes(validate_contract(m, CATALOG))


def test_deferred_axis_needs_a_target():
    m = _valid_meta()
    m["quality_axes"]["axes"]["performance@C"] = {"state": "deferred"}  # no deferred_to
    assert "C009" in _codes(validate_contract(m, CATALOG))


def test_n_a_axis_needs_a_signoff():
    m = _valid_meta()
    m["quality_axes"]["axes"]["performance@C"] = {"state": "n_a"}  # no signoff
    assert "C011" in _codes(validate_contract(m, CATALOG))
    m["quality_axes"]["axes"]["performance@C"] = {"state": "n_a", "signoff": "LeCun 2026-07-28"}
    assert "C011" not in _codes(validate_contract(m, CATALOG))


def test_acceptance_must_be_binary_and_identified():
    m = _valid_meta()
    m["acceptance"] = [{"must": "no id here"}]
    assert "C003" in _codes(validate_contract(m, CATALOG))


def test_unknown_profile_without_catalog_errors():
    m = _valid_meta()
    m["quality_axes"]["profiles"] = ["Z"]
    assert "C005" in _codes(validate_contract(m, CATALOG))


def test_missing_non_goals_is_a_warning_not_an_error():
    m = _valid_meta()
    del m["non_goals"]
    findings = validate_contract(m, CATALOG)
    assert "C010" in _codes(findings, level="warn")
    assert _codes(findings) == set()  # still no errors


def test_parse_requires_frontmatter():
    with pytest.raises(ContractError):
        parse_contract("no frontmatter here")
    meta, body = parse_contract("---\nid: y\n---\nbody text\n")
    assert meta["id"] == "y" and "body text" in body
