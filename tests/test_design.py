"""v0.6 — design-lens pack: persona_file loading, group filtering, and the builtin ADR gate."""


from trellis.config import TrellisConfig
from trellis.gates import run_gate
from trellis.review import LensResult, build_prompt, run_review

NOW = "2026-08-03T00:00:00+00:00"


def _cfg(gates=None):
    return TrellisConfig(axes={}, tiers={}, gates=gates or {}, path=None, raw={})


class TestPersonaFile:
    def test_persona_file_is_loaded_into_the_prompt(self, tmp_path):
        pf = tmp_path / "rubric.md"
        pf.write_text("RUBRIC-ABSTRACTION: judge substitutability.")
        prompt = build_prompt({"persona_file": str(pf)}, "CONTRACT", "DIFF")
        assert "RUBRIC-ABSTRACTION" in prompt and "CONTRACT" in prompt

    def test_missing_persona_file_falls_back_not_crash(self):
        prompt = build_prompt({"persona_file": "/no/such/file.md"}, "C", "D")
        assert "rigorous, independent reviewer" in prompt  # graceful fallback (A5)

    def test_inline_persona_takes_precedence(self, tmp_path):
        pf = tmp_path / "r.md"; pf.write_text("FROM-FILE")
        prompt = build_prompt({"persona": "INLINE", "persona_file": str(pf)}, "C", "D")
        assert "INLINE" in prompt and "FROM-FILE" not in prompt


class TestGroupFiltering:
    def _mock(self, lens, ct, diff, timeout):
        return LensResult(lens["name"], "SIGN", ["ok"])

    def test_group_runs_only_that_group(self, tmp_path):
        cfg = {"lenses": [
            {"name": "static", "group": "code"},
            {"name": "abstraction", "group": "design"},
            {"name": "domain", "group": "design"},
        ]}
        rec = run_review(None, cfg, "diff", now=NOW, group="design",
                         out_path=str(tmp_path / "d.json"), run_lens=self._mock)
        names = {l["name"] for l in rec["lenses"]}
        assert names == {"abstraction", "domain"}  # code lens excluded (A2)

    def test_no_group_runs_all(self, tmp_path):
        cfg = {"lenses": [{"name": "a", "group": "code"}, {"name": "b", "group": "design"}]}
        rec = run_review(None, cfg, "diff", now=NOW, out_path=str(tmp_path / "d.json"),
                         run_lens=self._mock)
        assert rec["metrics"]["lens_count"] == 2


class TestAdrGate:
    def _contract(self, tmp_path, cid="design-x"):
        c = tmp_path / "c.md"
        c.write_text(f"---\nid: {cid}\ngoal: g\ntier: design\n"
                     "acceptance: [{id: A1, must: x}]\n"
                     "quality_axes: {profiles: [C], axes: {correctness@C: {state: asserted}},"
                     " kpis: [{id: K1, axis: correctness, profile: C, must_have: true, target: t}]}\n---\nb\n")
        return str(c)

    def test_missing_dir_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        r = run_gate("adr", {"builtin": "adr", "dir": "docs/adr"}, _cfg(), None)
        assert r.ok is False and "no ADR directory" in r.detail

    def test_empty_dir_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "docs" / "adr").mkdir(parents=True)
        r = run_gate("adr", {"builtin": "adr", "dir": "docs/adr"}, _cfg(), None)
        assert r.ok is False and "no ADRs" in r.detail

    def test_present_passes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        d = tmp_path / "docs" / "adr"; d.mkdir(parents=True)
        (d / "0001-x.md").write_text("# ADR-1\nsome decision")
        r = run_gate("adr", {"builtin": "adr", "dir": "docs/adr"}, _cfg(), None)
        assert r.ok is True

    def test_must_reference_contract(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        contract = self._contract(tmp_path, "design-rate-limit")
        d = tmp_path / "docs" / "adr"; d.mkdir(parents=True)
        (d / "0001-other.md").write_text("# ADR-1\nunrelated")
        spec = {"builtin": "adr", "dir": "docs/adr", "must_reference_contract": True}
        r = run_gate("adr", spec, _cfg(), contract)
        assert r.ok is False and "references contract id" in r.detail
        # now add an ADR that references the design id
        (d / "0002-rate-limit.md").write_text("# ADR-2 for design-rate-limit\ndecision")
        r2 = run_gate("adr", spec, _cfg(), contract)
        assert r2.ok is True and "design-rate-limit" in r2.detail


def test_pack_ships_five_design_rubrics():
    from pathlib import Path
    import trellis
    lenses = Path(trellis.__file__).parent / "templates" / "lenses"
    files = sorted(p.name for p in lenses.glob("design.*.md"))
    assert len(files) == 5
