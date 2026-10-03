"""`greenbar accountability` — does the loop actually pay?

The differentiator: every "AI review / spec" tool *asserts* it helps; this *measures* it. Of the
changes that PASSED all gates, how many were later reverted (or flagged as incidents)? That's the
defect-escape rate — CTO-legible, and it makes the loop accountable.

Honest by construction: reverts are a **proxy** for defects (not every revert is a defect, not every
defect is reverted), and commits Greenbar never gated are reported as *ungoverned* — never as
escapes. Everything is computed from `git log` + `.greenbar/history.jsonl`; no external service.

The functions here are pure (git data is passed in), so the metric is fully testable without a repo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_REVERTS_RE = re.compile(r"This reverts commit ([0-9a-f]{7,40})", re.IGNORECASE)


@dataclass
class Commit:
    sha: str
    time: int          # unix epoch (commit time)
    subject: str = ""
    body: str = ""


@dataclass
class Report:
    gated_changes: int = 0
    reverts_total: int = 0
    escapes: int = 0
    ungoverned_reverts: int = 0
    incident_escapes: int = 0
    escape_rate: Optional[float] = None      # (escapes + incident_escapes) / gated_changes
    time_to_revert_days: List[float] = field(default_factory=list)


def _sha_match(target: str, shas) -> Optional[str]:
    """Match a (possibly abbreviated) revert target against known SHAs by prefix, either direction."""
    for s in shas:
        if s == target or s.startswith(target) or target.startswith(s):
            return s
    return None


def find_reverts(commits: List[Commit]) -> List[Tuple[str, str, int]]:
    """Return (revert_sha, reverted_target_sha, revert_time) for each revert commit."""
    out: List[Tuple[str, str, int]] = []
    for c in commits:
        m = _REVERTS_RE.search(c.body or "")
        if m:
            out.append((c.sha, m.group(1), c.time))
    return out


def gated_commits(events: List[dict]) -> Dict[str, dict]:
    """SHA -> the passing gate event for it (only gate events that passed AND carry a commit)."""
    out: Dict[str, dict] = {}
    for e in events:
        if e.get("kind") == "gate" and e.get("ok") and e.get("commit"):
            out[e["commit"]] = e
    return out


def compute(
    events: List[dict],
    commits: List[Commit],
    *,
    incidents: Optional[List[str]] = None,
    window_days: Optional[float] = None,
) -> Report:
    passed = gated_commits(events)
    commit_time = {c.sha: c.time for c in commits}
    reverts = find_reverts(commits)

    r = Report(gated_changes=len(passed), reverts_total=len(reverts))
    for _rev_sha, target, rev_time in reverts:
        hit = _sha_match(target, passed.keys())
        if hit is None:
            r.ungoverned_reverts += 1
            continue
        # optional window: only attribute a revert that lands within window_days of the merge
        base_time = commit_time.get(hit)
        if (window_days and base_time is not None and rev_time is not None
                and (rev_time - base_time) > window_days * 86400):
            continue
        r.escapes += 1
        if base_time is not None and rev_time is not None:
            r.time_to_revert_days.append(round((rev_time - base_time) / 86400, 2))

    if incidents:
        for sha in incidents:
            if _sha_match(sha, passed.keys()):
                r.incident_escapes += 1

    if r.gated_changes:
        r.escape_rate = (r.escapes + r.incident_escapes) / r.gated_changes
    return r


def format_report(r: Report) -> str:
    lines = [
        "Greenbar accountability  (revert-based defect-escape proxy)",
        "=" * 58,
        "",
        f"gated changes (passed all gates):  {r.gated_changes}",
        f"reverts in history:                {r.reverts_total}"
        f"  ({r.escapes} of gated → escaped, {r.ungoverned_reverts} ungoverned)",
    ]
    if r.incident_escapes:
        lines.append(f"incident-linked escapes:           {r.incident_escapes}")
    if r.escape_rate is not None:
        lines.append("")
        lines.append(f"ESCAPE RATE:  {r.escape_rate:.1%}   "
                     "← of gate-passed changes, this fraction was later reverted/incident-linked")
        if r.time_to_revert_days:
            avg = sum(r.time_to_revert_days) / len(r.time_to_revert_days)
            lines.append(f"mean time-to-revert:  {avg:.1f} days")
    else:
        lines.append("")
        lines.append("(no gate-passed commits in history yet — run `greenbar gate` in CI to accrue signal)")
    lines += [
        "",
        "note: reverts are a PROXY for defects — not every revert is a defect, not every defect is",
        "reverted. Commits Greenbar never gated are counted as 'ungoverned', not as escapes.",
    ]
    return "\n".join(lines)
