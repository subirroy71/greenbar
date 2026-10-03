"""A failing PR comment must be readable at a glance (contracts/pr-comment-readability.md)."""
from greenbar.render import render_pr_comment
from greenbar.review import failure_excerpt, plural, run_command_lens

PYTEST_FAIL = (
    "." * 72 + " [ 33%]\n" + "." * 12 + "F" + "." * 59 + " [ 67%]\n" + "." * 68 + "ss [100%]\n"
    "=================================== FAILURES ===================================\n"
    "_ TestThing.test_it _\n"
    "    def test_it():\n>       assert 1 == 2\nE       assert 1 == 2\n"
    "=========================== short test summary info ============================\n"
    "FAILED tests/test_x.py::TestThing::test_it - assert 1 == 2\n"
    "1 failed, 211 passed, 2 skipped in 3.89s\n"
)


class TestFailureExcerpt:
    def test_pytest_failure_shows_the_failing_test_not_progress(self):
        ex = failure_excerpt(PYTEST_FAIL)
        assert ex.splitlines()[0] == "FAILED tests/test_x.py::TestThing::test_it - assert 1 == 2"
        assert "1 failed, 211 passed" in ex
        assert "....." not in ex and "short test summary info" not in ex

    def test_non_pytest_output_keeps_the_last_lines(self):
        out = "\n".join(f"line {i}" for i in range(40))
        ex = failure_excerpt(out)
        assert ex.splitlines()[-1] == "line 39" and "line 0\n" not in ex

    def test_one_giant_line_keeps_its_end(self):
        ex = failure_excerpt("x" * 5000 + "THE END")
        assert len(ex) <= 800 and ex.endswith("THE END") and ex.startswith("…")

    def test_many_failures_trim_whole_lines_and_keep_the_first_name(self):
        out = "\n".join(f"FAILED tests/test_mod.py::test_case_{i} - AssertionError: boom" for i in range(60))
        ex = failure_excerpt(out)
        assert len(ex) <= 800
        assert ex.splitlines()[0] == "FAILED tests/test_mod.py::test_case_0 - AssertionError: boom"
        assert ex.splitlines()[-1].startswith("… ") and "more lines" in ex.splitlines()[-1]

    def test_no_summary_line_still_drops_progress_dots(self):
        ex = failure_excerpt("....F...                                   [100%]\n1 failed, 3 passed in 0.1s\n")
        assert ex == "1 failed, 3 passed in 0.1s"

    def test_real_pytest_output(self, tmp_path):
        import subprocess, sys
        (tmp_path / "test_real.py").write_text(
            "def test_ok():\n    assert True\n\ndef test_broken():\n    assert 1 + 1 == 3\n")
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
                              capture_output=True, text=True, cwd=tmp_path)
        assert proc.returncode == 1
        ex = failure_excerpt(proc.stdout + proc.stderr)
        assert ex.splitlines()[0].startswith("FAILED ") and "test_broken" in ex.splitlines()[0]
        assert "1 failed, 1 passed" in ex and "...." not in ex

    def test_deterministic_lens_records_the_excerpt(self, tmp_path):
        out = tmp_path / "pytest.out"
        out.write_text(PYTEST_FAIL)
        lens = {"name": "tests", "command": f"cat '{out}'; exit 1", "deterministic": True}
        r = run_command_lens(lens, "", "", timeout_s=10)
        assert r.verdict == "BLOCK" and r.findings[0].startswith("FAILED tests/test_x.py")


class TestPlural:
    def test_counts(self):
        assert plural(1, "lens", "lenses") == "1 lens"
        assert plural(2, "lens", "lenses") == "2 lenses"
        assert plural(0, "finding") == "0 findings" and plural(1, "finding") == "1 finding"


class TestRenderedComment:
    def _rec(self, finding):
        return {"summary": {"verdict": "BLOCKED"}, "metrics": {"lens_count": 1, "finding_count": 1},
                "lenses": [{"name": "tests", "verdict": "BLOCK", "findings": [finding]}]}

    def test_failing_comment_leads_with_the_failing_test(self):
        md = render_pr_comment(None, [("Code review", self._rec(failure_excerpt(PYTEST_FAIL)))])
        bullet = next(ln for ln in md.splitlines() if ln.startswith("- "))
        assert "FAILED tests/test_x.py::TestThing::test_it" in bullet
        assert "1 lens · 1 finding" in md

    def test_multiline_finding_folds_into_details(self):
        md = render_pr_comment(None, [("Code review", self._rec("first line\nsecond\n```oops"))])
        assert "- ⛔ _tests_ — first line" in md
        assert "<details><summary>full output</summary>" in md and "</details>" in md
        assert md.count("```") == 2  # the stray fence in the output can't close the block

    def test_single_line_finding_stays_inline(self):
        md = render_pr_comment(None, [("Code review", self._rec("rate limit is per-user"))])
        assert "- ⛔ _tests_ — rate limit is per-user" in md and "<details>" not in md
