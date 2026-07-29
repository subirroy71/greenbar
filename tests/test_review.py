"""`trellis review` — verdict parsing, orchestration/record, the real command provider (incl.
fail-closed on timeout/unparseable), and the review gate (missing/stale/blocked)."""
import json
from pathlib import Path

import pytest

from trellis.review import (
    LensResult,
    build_prompt,
    check_review_record,
    normalize_verdict,
    parse_verdict_json,
    run_command_lens,
    run_review,
)

NOW = "2026-07-29T00:00:00+00:00"


class TestParsing:
    def test_normalize_verdict_aliases(self):
        assert normalize_verdict("sign") == "SIGN"
        assert normalize_verdict("SIGN-WITH-CHANGE") == "SIGN_WITH_CHANGE"
        assert normalize_verdict("request changes") == "SIGN_WITH_CHANGE"
        assert normalize_verdict("reject") == "BLOCK"
        assert normalize_verdict(None) == "ERROR"
        assert normalize_verdict("garble") == "ERROR"

    def test_parse_last_json_with_verdict_after_prose(self):
        text = 'Here is my review... looks fine.\n{"verdict":"SIGN","findings":[]}'
        assert parse_verdict_json(text) == {"verdict": "SIGN", "findings": []}

    def test_parse_ignores_non_verdict_json_and_takes_last(self):
        text = '{"unrelated":1}\nmore\n{"verdict":"BLOCK","findings":["x"]}'
        assert parse_verdict_json(text)["verdict"] == "BLOCK"

    def test_parse_tolerates_braces_inside_findings(self):
        text = '{"verdict":"SIGN_WITH_CHANGE","findings":["use {} not dict() at foo.py:3"]}'
        assert parse_verdict_json(text)["findings"] == ["use {} not dict() at foo.py:3"]

    def test_parse_none_when_absent(self):
        assert parse_verdict_json("no json here at all") is None


class TestOrchestration:
    def _run(self, lens_specs, **kw):
        def mock(lens, contract_text, diff, timeout_s):
            return LensResult(lens["name"], lens["_v"], lens.get("_f", []))
        cfg = {"lenses": lens_specs, "review": {}}
        return run_review(None, cfg, "some diff", now=NOW, run_lens=mock, **kw)

    def test_all_sign_no_findings_flags_rubber_stamp(self, tmp_path):
        rec = self._run(
            [{"name": "a", "_v": "SIGN"}, {"name": "b", "_v": "SIGN"}],
            out_path=str(tmp_path / "r.json"),
        )
        assert rec["summary"]["verdict"] == "PASS"
        assert rec["metrics"]["all_sign_no_findings"] is True
        assert rec["metrics"]["sign_rate"] == 1.0

    def test_block_makes_overall_blocked(self, tmp_path):
        rec = self._run(
            [{"name": "a", "_v": "SIGN", "_f": ["nit"]}, {"name": "b", "_v": "BLOCK", "_f": ["boom"]}],
            out_path=str(tmp_path / "r.json"),
        )
        assert rec["summary"]["verdict"] == "BLOCKED"
        assert rec["summary"]["blockers"] == 1
        assert rec["metrics"]["all_sign_no_findings"] is False

    def test_change_makes_overall_changes(self, tmp_path):
        rec = self._run(
            [{"name": "a", "_v": "SIGN_WITH_CHANGE", "_f": ["rename x"]}],
            out_path=str(tmp_path / "r.json"),
        )
        assert rec["summary"]["verdict"] == "CHANGES"

    def test_record_is_written_with_hashes(self, tmp_path):
        out = tmp_path / "r.json"
        rec = self._run([{"name": "a", "_v": "SIGN"}], out_path=str(out))
        assert out.exists()
        on_disk = json.loads(out.read_text())
        assert on_disk["context_hash"] == rec["context_hash"] and rec["context_hash"]


class TestCommandProvider:
    def test_deterministic_lens_from_exit_code(self):
        ok = run_command_lens({"name": "ok", "command": "true", "deterministic": True}, "", "", 5)
        bad = run_command_lens({"name": "bad", "command": "false", "deterministic": True}, "", "", 5)
        assert ok.verdict == "SIGN" and bad.verdict == "BLOCK"

    def test_llm_lens_parses_json(self):
        r = run_command_lens(
            {"name": "x", "command": "echo '{\"verdict\":\"sign\",\"findings\":[\"nit\"]}'"}, "", "", 5
        )
        assert r.verdict == "SIGN" and r.findings == ["nit"]

    def test_unparseable_output_is_error_not_sign(self):
        # fail-closed: a lens that prints no verdict JSON must NOT count as a pass
        r = run_command_lens({"name": "x", "command": "echo 'looks good to me'"}, "", "", 5)
        assert r.verdict == "ERROR"

    def test_timeout_is_error(self):
        r = run_command_lens({"name": "slow", "command": "sleep 2"}, "", "", 0.2)
        assert r.verdict == "ERROR" and "timed out" in (r.error or "")

    def test_prompt_includes_persona_contract_and_diff(self):
        p = build_prompt({"persona": "PERSONA-X"}, "CONTRACT-Y", "DIFF-Z")
        assert "PERSONA-X" in p and "CONTRACT-Y" in p and "DIFF-Z" in p and '"verdict"' in p


class TestReviewGate:
    def test_missing_record_fails(self, tmp_path):
        ok, msg = check_review_record(None, str(tmp_path / "none.json"))
        assert ok is False and "no review record" in msg

    def test_blocked_record_fails(self, tmp_path):
        rec = {"summary": {"verdict": "BLOCKED", "blockers": 1}, "metrics": {"lens_count": 2}}
        p = tmp_path / "r.json"; p.write_text(json.dumps(rec))
        ok, msg = check_review_record(None, str(p))
        assert ok is False and "BLOCKED" in msg

    def test_pass_record_ok(self, tmp_path):
        rec = {"summary": {"verdict": "PASS"}, "metrics": {"lens_count": 3, "all_sign_no_findings": False}}
        p = tmp_path / "r.json"; p.write_text(json.dumps(rec))
        ok, _ = check_review_record(None, str(p))
        assert ok is True

    def test_stale_record_fails(self, tmp_path):
        contract = tmp_path / "c.md"; contract.write_text("---\nid: x\n---\nv1\n")
        rec = {"contract_hash": "deadbeefdeadbeef", "summary": {"verdict": "PASS"}, "metrics": {}}
        p = tmp_path / "r.json"; p.write_text(json.dumps(rec))
        ok, msg = check_review_record(str(contract), str(p))
        assert ok is False and "STALE" in msg

    def test_rubber_stamp_fails_when_configured(self, tmp_path):
        rec = {"summary": {"verdict": "PASS"}, "metrics": {"all_sign_no_findings": True, "lens_count": 4}}
        p = tmp_path / "r.json"; p.write_text(json.dumps(rec))
        ok, msg = check_review_record(None, str(p), fail_on_rubber_stamp=True)
        assert ok is False and "rubber stamp" in msg
        ok2, _ = check_review_record(None, str(p), fail_on_rubber_stamp=False)
        assert ok2 is True
