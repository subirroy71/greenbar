"""Render the latest gate + review artifacts into a Markdown PR summary.

Separation of concerns: this turns what `gate`/`review` already produced into Markdown (with a
stable marker so a workflow can update ONE comment instead of spamming). The CLI renders; the
GitHub Action posts. No hosted service, no invented findings.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

MARKER = "<!-- greenbar-report -->"

_ICON = {
    "PASS": "✅", "CHANGES": "🔸", "BLOCKED": "⛔", "NO_LENSES": "⛔",
    "SIGN": "✅", "SIGN_WITH_CHANGE": "🔸", "BLOCK": "⛔", "ERROR": "⚠️",
}


def render_pr_comment(
    gate_event: Optional[dict],
    reviews: Optional[List[Tuple[str, dict]]] = None,
) -> str:
    reviews = reviews or []
    out: List[str] = ["## 🟩 Greenbar"]

    if gate_event:
        tier = gate_event.get("tier", "?")
        ok = bool(gate_event.get("ok"))
        out.append(f"**Gate `{tier}`: {'✅ pass' if ok else '⛔ FAIL — blocks merge'}**")
        gates = gate_event.get("gates") or []
        if gates:
            out += ["", "| gate | result |", "|---|---|"]
            out += [f"| `{g.get('name')}` | {'✅' if g.get('ok') else '❌'} |" for g in gates]
        out.append("")
    else:
        out += ["_no gate run recorded yet_", ""]

    for label, rec in reviews:
        if not rec:
            continue
        summary = rec.get("summary") or {}
        metrics = rec.get("metrics") or {}
        verdict = summary.get("verdict", "?")
        line = (f"**{label}: {_ICON.get(verdict, '')} {verdict}** · "
                f"{metrics.get('lens_count', 0)} lenses · {metrics.get('finding_count', 0)} findings")
        if metrics.get("all_sign_no_findings"):
            line += "  ⚠️ _all-SIGN / zero findings — possible rubber stamp_"
        out += [line, ""]
        for lens in rec.get("lenses") or []:
            for f in lens.get("findings") or []:
                out.append(f"- {_ICON.get(lens.get('verdict'), '')} _{lens.get('name')}_ — {f}")
            if lens.get("error"):
                out.append(f"- ⚠️ _{lens.get('name')}_ — {lens['error']}")
        out.append("")

    out.append("<sub>via `greenbar gate` + `greenbar render` — the gate is a required check.</sub>")
    out.append(MARKER)
    return "\n".join(out).strip()
