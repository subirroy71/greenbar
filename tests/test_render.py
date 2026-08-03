"""v0.9 — Markdown PR rendering + the CLI render command."""
import json
from pathlib import Path

from trellis.cli import main
from trellis.render import MARKER, render_pr_comment


def _gate(ok=True):
    return {"kind": "gate", "tier": "critical", "ok": ok,
            "gates": [{"name": "contract", "ok": True}, {"name": "test", "ok": ok},
                      {"name": "review", "ok": True}]}


def _review(verdict="CHANGES", findings=("nit at x.py:3",), all_sign=False):
    return {"summary": {"verdict": verdict},
            "metrics": {"lens_count": 2, "finding_count": len(findings),
                        "all_sign_no_findings": all_sign},
            "lenses": [{"name": "security", "verdict": "SIGN_WITH_CHANGE", "findings": list(findings)}]}


class TestRender:
    def test_gate_table_and_overall(self):
        md = render_pr_comment(_gate(ok=True), [])
        assert "Gate `critical`: ✅ pass" in md
        assert "| `contract` | ✅ |" in md and "| `test` | ✅ |" in md
        assert MARKER in md  # A3 — stable marker for comment upsert

    def test_failing_gate_says_blocks_merge(self):
        md = render_pr_comment(_gate(ok=False), [])
        assert "FAIL — blocks merge" in md and "| `test` | ❌ |" in md

    def test_review_verdict_and_findings(self):
        md = render_pr_comment(_gate(), [("Code review", _review())])
        assert "Code review: 🔸 CHANGES" in md and "2 lenses · 1 findings" in md
        assert "_security_ — nit at x.py:3" in md  # A2

    def test_rubber_stamp_flagged(self):
        md = render_pr_comment(_gate(), [("Code review", _review(verdict="PASS", findings=(), all_sign=True))])
        assert "rubber stamp" in md.lower()

    def test_missing_artifacts_do_not_crash(self):
        md = render_pr_comment(None, [])  # A5
        assert "no gate run recorded" in md and MARKER in md


class TestRenderCLI:
    def test_render_reads_history_and_review(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".trellis").mkdir()
        (tmp_path / ".trellis" / "history.jsonl").write_text(json.dumps(_gate()) + "\n")
        (tmp_path / ".trellis" / "review-record.json").write_text(json.dumps(_review()))
        assert main(["render"]) == 0
        out = capsys.readouterr().out
        assert "🌿 Trellis" in out and "Code review" in out and MARKER in out

    def test_render_out_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".trellis").mkdir()
        (tmp_path / ".trellis" / "history.jsonl").write_text(json.dumps(_gate()) + "\n")
        assert main(["render", "--out", "c.md"]) == 0
        assert MARKER in (tmp_path / "c.md").read_text()


def test_pr_workflow_template_ships():
    import trellis
    wf = Path(trellis.__file__).parent / "templates" / "github" / "trellis-pr.yml"
    assert wf.exists() and "trellis gate --auto" in wf.read_text()  # A4
