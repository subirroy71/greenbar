"""Append-only run history (`.greenbar/history.jsonl`) — the substrate for `greenbar report`.

Every `gate`/`review` appends one JSON line. Kept local + line-delimited so it's cheap to write,
trivial to tail, and robust to a partial write (a corrupt line is skipped, not fatal). Gitignored
by default (local telemetry).

CI runners are ephemeral, so the local file never survives there. For a durable, shared record,
`greenbar gate --notes` also attaches the event as a git note (``refs/notes/greenbar``) on the gated
commit; push that ref and `report`/`accountability` read it back from any clone.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_HISTORY = ".greenbar/history.jsonl"
NOTES_REF = "greenbar"


def record_event(event: Dict, path: str = DEFAULT_HISTORY) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def read_events(path: str = DEFAULT_HISTORY) -> List[Dict]:
    p = Path(path)
    if not p.exists():
        return []
    events: List[Dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # skip a torn/partial line rather than crash the report
    return events


def current_commit() -> Optional[str]:
    """The commit a gate result is about. ``GREENBAR_COMMIT`` overrides HEAD — in a GitHub
    ``pull_request`` run HEAD is a throwaway merge commit that no later revert will ever name."""
    env = os.environ.get("GREENBAR_COMMIT", "").strip()
    if env:
        return env
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def record_note(event: Dict, commit: Optional[str], ref: str = NOTES_REF) -> bool:
    """Append ``event`` as a git note on ``commit``. Returns False (never raises) if git can't."""
    if not commit:
        return False
    try:
        proc = subprocess.run(
            ["git", "notes", f"--ref={ref}", "append", "-m", json.dumps(event, sort_keys=True), commit],
            capture_output=True, text=True,
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001 — no git → the local history still has the event
        return False


def read_note_events(ref: str = NOTES_REF) -> List[Dict]:
    """Every event stored in ``refs/notes/<ref>`` (one JSON object per note line); [] without git."""
    def git(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True)

    try:
        listing = git("notes", f"--ref={ref}", "list")
    except Exception:  # noqa: BLE001
        return []
    if listing.returncode != 0:
        return []
    events: List[Dict] = []
    for row in listing.stdout.splitlines():
        parts = row.split()
        if len(parts) != 2:
            continue
        shown = git("notes", f"--ref={ref}", "show", parts[1])
        for line in shown.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(ev, dict):
                ev.setdefault("commit", parts[1])
                events.append(ev)
    return events


def read_all_events(path: str = DEFAULT_HISTORY, ref: str = NOTES_REF) -> List[Dict]:
    """Local history plus git-notes history, de-duplicated (the same event can be in both)."""
    seen = set()
    out: List[Dict] = []
    for ev in read_events(path) + read_note_events(ref):
        key = json.dumps(ev, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out
