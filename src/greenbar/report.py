"""`greenbar report` — aggregate the run history into signal about the loop itself.

Answers "is the ceremony paying?": gate pass-rate + which gates fail most, review verdict
distribution + the rubber-stamp rate (all-SIGN/zero-findings) over time. Metrics that can only be
proxies are labelled as proxies — no overclaiming a true defect-escape number.
"""
from __future__ import annotations

from typing import Dict, List


def aggregate(events: List[Dict]) -> Dict:
    gates = [e for e in events if e.get("kind") == "gate"]
    reviews = [e for e in events if e.get("kind") == "review"]

    g_pass = sum(1 for e in gates if e.get("ok"))
    failures_by_gate: Dict[str, int] = {}
    tier_counts: Dict[str, int] = {}
    for e in gates:
        tier_counts[e.get("tier", "?")] = tier_counts.get(e.get("tier", "?"), 0) + 1
        for g in e.get("gates", []):
            if not g.get("ok"):
                failures_by_gate[g["name"]] = failures_by_gate.get(g["name"], 0) + 1

    verdicts: Dict[str, int] = {}
    rubber = findings = 0
    for e in reviews:
        verdicts[e.get("verdict", "?")] = verdicts.get(e.get("verdict", "?"), 0) + 1
        if e.get("all_sign_no_findings"):
            rubber += 1
        findings += int(e.get("finding_count", 0))

    return {
        "gate": {
            "runs": len(gates),
            "pass_rate": (g_pass / len(gates)) if gates else None,
            "tier_counts": tier_counts,
            "failures_by_gate": dict(sorted(failures_by_gate.items(), key=lambda kv: -kv[1])),
        },
        "review": {
            "runs": len(reviews),
            "verdicts": verdicts,
            # proxy: how often the panel surfaced something (a stand-in for "caught at authoring")
            "review_catch_rate_proxy": (
                sum(v for k, v in verdicts.items() if k in ("CHANGES", "BLOCKED")) / len(reviews)
                if reviews else None
            ),
            "rubber_stamp_rate": (rubber / len(reviews)) if reviews else None,
            "avg_findings": (findings / len(reviews)) if reviews else None,
        },
    }


def signals(agg: Dict) -> List[str]:
    """Heuristic warnings worth a human's eye — a report is only useful if it flags trouble."""
    out: List[str] = []
    r = agg["review"]
    if r["runs"] >= 3 and (r["rubber_stamp_rate"] or 0) > 0.5:
        out.append("⚠ over half of reviews were all-SIGN with zero findings — possible rubber-stamping "
                   "(diversify lenses / go cross-model / prompt for refutation).")
    g = agg["gate"]
    if g["runs"] >= 10 and g["pass_rate"] == 1.0:
        out.append("⚠ 100% gate pass-rate over many runs — gates may be too weak to ever fail "
                   "(are they catching anything?).")
    if r["runs"] == 0 and g["runs"] > 0:
        out.append("ℹ gates are running but no reviews are logged — is the `review` gate wired into "
                   "your critical tier?")
    return out


def format_report(agg: Dict) -> str:
    g, r = agg["gate"], agg["review"]
    lines = ["Greenbar report", "=" * 40, ""]
    lines.append(f"gate runs:        {g['runs']}")
    if g["runs"]:
        lines.append(f"  pass rate:      {g['pass_rate']:.0%}")
        lines.append(f"  by tier:        {g['tier_counts']}")
        if g["failures_by_gate"]:
            lines.append(f"  failures/gate:  {g['failures_by_gate']}")
    lines.append("")
    lines.append(f"review runs:      {r['runs']}")
    if r["runs"]:
        lines.append(f"  verdicts:       {r['verdicts']}")
        lines.append(f"  catch-rate*:    {r['review_catch_rate_proxy']:.0%}   (*proxy: CHANGES+BLOCKED / reviews)")
        lines.append(f"  rubber-stamp:   {r['rubber_stamp_rate']:.0%}   (all-SIGN, zero findings)")
        lines.append(f"  avg findings:   {r['avg_findings']:.1f}")
    sig = signals(agg)
    if sig:
        lines += ["", "signals:"] + [f"  {s}" for s in sig]
    return "\n".join(lines)
