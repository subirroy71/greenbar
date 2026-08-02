"""Append-only run history (`.trellis/history.jsonl`) — the substrate for `trellis report`.

Every `gate`/`review` appends one JSON line. Kept local + line-delimited so it's cheap to write,
trivial to tail, and robust to a partial write (a corrupt line is skipped, not fatal). Gitignored
by default (local telemetry); un-ignore it if you want an org-wide committed record.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

DEFAULT_HISTORY = ".trellis/history.jsonl"


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
