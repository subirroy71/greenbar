"""Pre-release hardening: the cheapest path to a green build must not skip the rigor.

Each test pins one enforcement hole found in review: placeholder contracts, undefined tiers,
target-less KPIs, malformed-contract crashes, stale reviews of changed code, zero-lens reviews,
hung gates, and gate history that never survived an ephemeral CI runner.
"""
import json
import subprocess

import pytest

from greenbar.cli import main
from greenbar.config import GreenbarConfig
from greenbar.contract import parse_contract, validate_contract
from greenbar.gates import run_gate
from greenbar.history import current_commit, read_all_events, read_note_events, record_note
from greenbar.review import LensResult, check_review_record, run_review, worktree_fingerprint

CATALOG = {"C": ["correctness"]}
GOOD = """---
id: x
goal: "ship x · measurable · constraint"
tier: scoped
non_goals: ["y"]
acceptance: [{id: A1, must: "x returns 1"}]
quality_axes:
  profiles: [C]
  axes: {correctness@C: {state: asserted}}
  kpis: [{id: K1, axis: correctness, profile: C, must_have: true, target: "0 failing criteria"}]
---
body
"""


def _codes(text, tiers=None):
    meta, _ = parse_contract(text)
    return {f.code for f in validate_contract(meta, CATALOG, tiers=tiers) if f.level == "error"}


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "app.py").write_text("x = 1\n")
    _git(tmp_path, "add", "app.py")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


class TestContractEnforcement:
    def test_good_contract_is_clean(self):
        assert _codes(GOOD, tiers=["scoped"]) == set()

    @pytest.mark.parametrize("marker", ["TODO", "TBD", "FIXME"])
    def test_placeholder_target_is_an_error(self, marker):
        assert "C012" in _codes(GOOD.replace("0 failing criteria", f"{marker} — fill me"))

    def test_mentioning_a_marker_in_prose_is_not_a_placeholder(self):
        assert "C012" not in _codes(GOOD.replace("x returns 1", "lint rejects TODO targets"))

    def test_placeholder_goal_and_acceptance_are_errors(self):
        assert "C012" in _codes(GOOD.replace("ship x · measurable · constraint", "TODO"))
        assert "C012" in _codes(GOOD.replace("x returns 1", "TODO — criterion"))

    def test_undefined_tier_is_an_error_only_when_tiers_known(self):
        bogus = GOOD.replace("tier: scoped", "tier: bogus-tier")
        assert "C013" in _codes(bogus, tiers=["trivial", "scoped"])
        assert "C013" not in _codes(bogus)  # no config → can't judge

    def test_musthave_kpi_without_target_is_an_error(self):
        codes = _codes(GOOD.replace(', target: "0 failing criteria"', ""))
        assert {"C014", "C008"} <= codes  # target-less KPI doesn't back the asserted axis

    def test_lint_on_malformed_contract_is_a_clean_failure(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        main(["init"])
        bad = tmp_path / "bad.md"
        bad.write_text("no frontmatter here\n")
        assert main(["lint", str(bad)]) == 1
        out = capsys.readouterr().out
        assert "C000" in out and "Traceback" not in out

    def test_contract_gate_rejects_undefined_tier(self, tmp_path):
        c = tmp_path / "c.md"
        c.write_text(GOOD.replace("tier: scoped", "tier: nope"))
        cfg = GreenbarConfig(axes=CATALOG, tiers={"scoped": {}}, gates={}, path=tmp_path, raw={})
        r = run_gate("contract", {"builtin": "contract"}, cfg, str(c))
        assert r.ok is False and "C013" in r.detail


class TestReviewFreshness:
    @staticmethod
    def _signing_lens(lens, contract, diff, timeout):
        return LensResult(lens["name"], "SIGN", ["looked at it"])

    def _review(self, out):
        return run_review(None, {"lenses": [{"name": "a"}]}, "diff", now="t", out_path=str(out),
                          run_lens=self._signing_lens)

    def test_fingerprint_is_content_addressed(self, repo):
        before = worktree_fingerprint()
        assert before
        (repo / "app.py").write_text("x = 2\n")
        edited = worktree_fingerprint()
        assert edited != before
        _git(repo, "commit", "-q", "-am", "edit")
        assert worktree_fingerprint() == edited  # committing the same content keeps it fresh

    def test_fingerprint_leaves_the_real_index_alone(self, repo):
        (repo / "app.py").write_text("x = 3\n")
        worktree_fingerprint()
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=repo,
                                capture_output=True, text=True).stdout
        assert staged == ""

    def test_review_of_older_code_is_stale(self, repo):
        out = repo / ".greenbar" / "review-record.json"
        self._review(out)
        ok, _ = check_review_record(None, str(out))
        assert ok is True
        (repo / "app.py").write_text("x = 'changed after review'\n")
        ok, msg = check_review_record(None, str(out))
        assert ok is False and "STALE" in msg and "code changed" in msg

    def test_record_without_fingerprint_is_stale_in_a_repo(self, repo):
        out = repo / "r.json"
        out.write_text(json.dumps({"summary": {"verdict": "PASS"}, "metrics": {"lens_count": 1}}))
        ok, msg = check_review_record(None, str(out))
        assert ok is False and "STALE" in msg

    def test_greenbar_artifacts_dont_affect_freshness(self, repo):
        out = repo / ".greenbar" / "review-record.json"
        self._review(out)
        (repo / ".greenbar" / "history.jsonl").write_text("{}\n")
        assert check_review_record(None, str(out))[0] is True


class TestZeroLenses:
    def test_zero_lenses_is_not_a_pass(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rec = run_review(None, {"lenses": []}, "", now="t", out_path=str(tmp_path / "r.json"))
        assert rec["summary"]["verdict"] == "NO_LENSES"
        ok, msg = check_review_record(None, str(tmp_path / "r.json"))
        assert ok is False and "zero lenses" in msg

    def test_cli_review_exits_nonzero_with_no_lenses(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "greenbar.yaml").write_text("axes: {C: [correctness]}\n")
        (tmp_path / "d.diff").write_text("")
        assert main(["review", "--diff", "d.diff"]) == 1


class TestRunGateTimeout:
    def test_hung_command_fails_the_gate(self, tmp_path):
        cfg = GreenbarConfig(axes={}, tiers={}, gates={}, path=tmp_path, raw={})
        r = run_gate("slow", {"run": "sleep 5", "timeout_s": 0.2}, cfg, None)
        assert r.ok is False and "timed out" in r.detail

    def test_global_timeout_applies(self, tmp_path):
        cfg = GreenbarConfig(axes={}, tiers={}, gates={}, path=tmp_path, raw={"gate_timeout_s": 0.2})
        assert run_gate("slow", {"run": "sleep 5"}, cfg, None).ok is False


class TestDurableHistory:
    def test_greenbar_commit_env_overrides_head(self, repo, monkeypatch):
        monkeypatch.setenv("GREENBAR_COMMIT", "abc123")
        assert current_commit() == "abc123"
        monkeypatch.delenv("GREENBAR_COMMIT")
        assert len(current_commit()) == 40

    def test_note_round_trip(self, repo):
        sha = current_commit()
        assert record_note({"kind": "gate", "ok": True, "commit": sha}, sha)
        assert record_note({"kind": "gate", "ok": False, "commit": sha}, sha)  # appends
        events = read_note_events()
        assert [e["ok"] for e in events] == [True, False]

    def test_read_all_dedupes_file_and_notes(self, repo):
        sha = current_commit()
        ev = {"kind": "gate", "ok": True, "commit": sha}
        record_note(ev, sha)
        (repo / "h.jsonl").write_text(json.dumps(ev) + "\n")
        assert read_all_events(str(repo / "h.jsonl")) == [ev]

    def test_gate_notes_feed_accountability_after_local_history_is_gone(self, repo, capsys):
        (repo / "greenbar.yaml").write_text(
            "tiers: {t: {gates: [ok]}}\ngates: {ok: {run: 'true'}}\n")
        (repo / "feature.py").write_text("f = 1\n")
        _git(repo, "add", "feature.py")
        _git(repo, "commit", "-q", "-m", "feature")
        assert main(["gate", "t", "--notes"]) == 0
        gated = current_commit()
        (repo / ".greenbar" / "history.jsonl").unlink()  # the ephemeral runner is gone
        (repo / "app.py").write_text("x = 9\n")
        _git(repo, "commit", "-q", "-am", "next")
        _git(repo, "revert", "--no-edit", gated)
        capsys.readouterr()
        assert main(["accountability", "--json"]) == 0
        rep = json.loads(capsys.readouterr().out)
        assert rep["gated_changes"] == 1 and rep["escapes"] == 1

    def test_mcp_gate_records_history(self, repo):
        from greenbar.mcp_server import handle
        (repo / "greenbar.yaml").write_text("tiers: {t: {gates: [ok]}}\ngates: {ok: {run: 'true'}}\n")
        handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "greenbar_gate", "arguments": {"tier": "t"}}})
        lines = (repo / ".greenbar" / "history.jsonl").read_text().splitlines()
        assert json.loads(lines[-1])["kind"] == "gate"
