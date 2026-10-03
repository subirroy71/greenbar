"""History logging + `greenbar report` aggregation and signals."""
from greenbar.history import read_events, record_event
from greenbar.report import aggregate, format_report, signals


class TestHistory:
    def test_roundtrip(self, tmp_path):
        h = str(tmp_path / "history.jsonl")
        record_event({"kind": "gate", "ok": True}, h)
        record_event({"kind": "review", "verdict": "PASS"}, h)
        events = read_events(h)
        assert len(events) == 2 and events[0]["kind"] == "gate"

    def test_absent_history_is_empty(self, tmp_path):
        assert read_events(str(tmp_path / "none.jsonl")) == []

    def test_torn_line_skipped_not_fatal(self, tmp_path):
        h = tmp_path / "history.jsonl"
        h.write_text('{"kind":"gate","ok":true}\n{not valid json\n{"kind":"review"}\n')
        assert len(read_events(str(h))) == 2


def _events():
    return [
        {"kind": "gate", "tier": "scoped", "ok": True, "gates": [{"name": "test", "ok": True}]},
        {"kind": "gate", "tier": "scoped", "ok": False,
         "gates": [{"name": "test", "ok": False}, {"name": "contract", "ok": True}]},
        {"kind": "gate", "tier": "critical", "ok": True, "gates": []},
        {"kind": "review", "verdict": "PASS", "finding_count": 0, "all_sign_no_findings": True},
        {"kind": "review", "verdict": "CHANGES", "finding_count": 3, "all_sign_no_findings": False},
        {"kind": "review", "verdict": "BLOCKED", "finding_count": 1, "all_sign_no_findings": False},
    ]


class TestAggregate:
    def test_gate_metrics(self):
        g = aggregate(_events())["gate"]
        assert g["runs"] == 3
        assert abs(g["pass_rate"] - 2 / 3) < 1e-9
        assert g["failures_by_gate"] == {"test": 1}
        assert g["tier_counts"] == {"scoped": 2, "critical": 1}

    def test_review_metrics(self):
        r = aggregate(_events())["review"]
        assert r["runs"] == 3
        assert r["verdicts"] == {"PASS": 1, "CHANGES": 1, "BLOCKED": 1}
        assert abs(r["review_catch_rate_proxy"] - 2 / 3) < 1e-9  # CHANGES+BLOCKED / 3
        assert abs(r["rubber_stamp_rate"] - 1 / 3) < 1e-9
        assert abs(r["avg_findings"] - 4 / 3) < 1e-9

    def test_empty_history_does_not_crash(self):
        agg = aggregate([])
        assert agg["gate"]["runs"] == 0 and agg["gate"]["pass_rate"] is None
        # formatting an empty report must also not crash
        assert "Greenbar report" in format_report(agg)


class TestSignals:
    def test_rubber_stamp_warning(self):
        evs = [{"kind": "review", "verdict": "PASS", "all_sign_no_findings": True, "finding_count": 0}
               for _ in range(4)]
        assert any("rubber-stamp" in s for s in signals(aggregate(evs)))
