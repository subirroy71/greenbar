"""v0.8 — the accountability metric: revert parsing, escape linkage, honest handling."""
from trellis.accountability import Commit, compute, find_reverts, format_report, gated_commits

DAY = 86400


def _gate(sha, ok=True):
    return {"kind": "gate", "ok": ok, "commit": sha, "gates": []}


class TestReverts:
    def test_find_reverts_parses_target_sha(self):
        commits = [
            Commit("rev1", 100, 'Revert "add feature"', "This reverts commit abcdef1234567890."),
            Commit("plain", 90, "add feature", "did a thing"),
        ]
        rv = find_reverts(commits)
        assert rv == [("rev1", "abcdef1234567890", 100)]

    def test_no_revert_body_ignored(self):
        assert find_reverts([Commit("x", 1, "normal", "nothing here")]) == []


class TestGatedCommits:
    def test_only_passing_gate_events_with_commit(self):
        events = [_gate("a"), _gate("b", ok=False), {"kind": "gate", "ok": True}, {"kind": "review"}]
        assert set(gated_commits(events)) == {"a"}  # 'b' failed; the no-commit event excluded


class TestCompute:
    def test_escape_when_reverted_commit_had_passing_gate(self):
        events = [_gate("feedface00000000")]
        commits = [
            Commit("feedface00000000", 10 * DAY, "the change", ""),
            Commit("rev", 12 * DAY, "Revert", "This reverts commit feedface00000000."),
        ]
        r = compute(events, commits)
        assert r.gated_changes == 1 and r.escapes == 1 and r.ungoverned_reverts == 0
        assert abs(r.escape_rate - 1.0) < 1e-9
        assert r.time_to_revert_days == [2.0]

    def test_revert_of_ungoverned_commit_is_not_an_escape(self):
        events = [_gate("governed0000")]
        commits = [
            Commit("governed0000", DAY, "ok", ""),
            Commit("rev", 2 * DAY, "Revert", "This reverts commit cafebabe9999."),  # not gated
        ]
        r = compute(events, commits)
        assert r.escapes == 0 and r.ungoverned_reverts == 1  # A4

    def test_short_sha_revert_matches_full_gated_sha(self):
        events = [_gate("abcdef1234567890abcdef")]
        commits = [Commit("rev", 1, "Revert", "This reverts commit abcdef1.")]  # abbreviated
        assert compute(events, commits).escapes == 1

    def test_window_excludes_late_reverts(self):
        events = [_gate("c0ffee00")]
        commits = [
            Commit("c0ffee00", 0, "change", ""),
            Commit("rev", 400 * DAY, "Revert", "This reverts commit c0ffee00."),
        ]
        assert compute(events, commits, window_days=30).escapes == 0  # too late to attribute

    def test_incidents_add_escapes(self):
        events = [_gate("deadbeef11"), _gate("deadbeef22")]
        r = compute(events, [], incidents=["deadbeef11"])
        assert r.incident_escapes == 1 and abs(r.escape_rate - 0.5) < 1e-9  # 1 of 2 gated

    def test_empty_inputs_do_not_crash(self):
        r = compute([], [])
        assert r.gated_changes == 0 and r.escape_rate is None
        assert "Trellis accountability" in format_report(r)  # A5 — proxy label present

    def test_output_labels_reverts_as_proxy(self):
        out = format_report(compute([_gate("x")], []))
        assert "proxy" in out.lower()
