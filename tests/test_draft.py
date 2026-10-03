"""v0.7 — `trellis draft` (PRD → lint-clean contract) + stack presets."""

from trellis.cli import main
from trellis.contract import parse_contract, validate_contract
from trellis.draft import ParsedPRD, build_contract, parse_prd

_CATALOG = {"C": ["correctness", "reasonableness"]}

_PRD = """# PRD-014 Login rate limiting
**Requirement:** cap login attempts to 5 per minute per username.
## Acceptance
- the 6th attempt within 60s returns throttled and does not check credentials
- a successful login resets the counter
## Out of scope
- per-IP limiting
- CAPTCHA
"""


class TestParsePRD:
    def test_pulls_goal_nongoals_acceptance(self):
        p = parse_prd(_PRD)
        assert "cap login attempts" in p.goal.lower()
        assert any("6th attempt" in a for a in p.acceptance)
        assert any("successful login resets" in a for a in p.acceptance)
        assert "per-IP limiting" in p.non_goals and "CAPTCHA" in p.non_goals

    def test_inline_out_of_scope_list(self):
        p = parse_prd("**Requirement:** do X\n**Out of scope:** a, b; c\n")
        assert p.non_goals == ["a", "b", "c"]

    def test_unstructured_prd_still_parses(self):
        p = parse_prd("just some freeform text about a feature")
        assert isinstance(p, ParsedPRD)  # no crash


class TestBuildContract:
    def test_drafted_contract_is_structurally_valid_but_not_gate_ready(self):
        content = build_contract(parse_prd(_PRD), "prd-014-rate-limit", "critical", _CATALOG, _PRD)
        meta, _ = parse_contract(content)
        errors = [f for f in validate_contract(meta, _CATALOG) if f.level == "error"]
        # structurally valid out of the box: the only errors are the TODO targets left to fill
        assert errors and {f.code for f in errors} == {"C012"}

    def test_filled_draft_lints_clean(self):
        content = build_contract(parse_prd(_PRD), "prd-014-rate-limit", "critical", _CATALOG, _PRD)
        content = content.replace("TODO — a behavioral target (error-rate / effect-size / equality)",
                                  "0 failing acceptance criteria")
        meta, _ = parse_contract(content)
        assert [f for f in validate_contract(meta, _CATALOG) if f.level == "error"] == []

    def test_every_axis_asserted_with_a_musthave_kpi(self):
        meta, _ = parse_contract(build_contract(ParsedPRD(goal="g"), "x", "scoped", _CATALOG))
        axes = meta["quality_axes"]["axes"]
        assert set(axes) == {"correctness@C", "reasonableness@C"}
        must = {(k["axis"], k["profile"]) for k in meta["quality_axes"]["kpis"] if k["must_have"]}
        assert must == {("correctness", "C"), ("reasonableness", "C")}

    def test_empty_acceptance_gets_a_placeholder(self):
        meta, _ = parse_contract(build_contract(ParsedPRD(), "x", "scoped", _CATALOG))
        assert len(meta["acceptance"]) == 1 and "TODO" in meta["acceptance"][0]["must"]


class TestDraftCLI:
    def test_draft_writes_a_lintable_contract(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main(["init"])  # gives an axis catalog
        (tmp_path / "PRD.md").write_text(_PRD)
        assert main(["draft", "PRD.md", "--id", "rate-limit"]) == 0
        out = tmp_path / "contracts" / "rate-limit.md"
        assert out.exists()
        # an unfilled draft must not pass the gate — the cheapest path can't be a green build
        assert main(["lint", str(out)]) == 1
        out.write_text(out.read_text().replace(
            "TODO — a behavioral target (error-rate / effect-size / equality)", "0 failing criteria"))
        assert main(["lint", str(out)]) == 0


class TestPresets:
    def test_init_preset_writes_stack_gates(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert main(["init", "--preset", "go"]) == 0
        cfg = (tmp_path / "trellis.yaml").read_text()
        assert "go test ./..." in cfg and "go vet ./..." in cfg  # A5

    def test_unknown_preset_falls_back_to_generic(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert main(["init", "--preset", "cobol"]) == 0
        assert (tmp_path / "trellis.yaml").exists()  # fell back, no crash
