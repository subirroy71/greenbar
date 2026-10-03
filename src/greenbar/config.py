"""Project-level Greenbar config (`greenbar.yaml`): the axis catalog, tiers, and gates.

Kept separate from the per-change contract: the config is the project's *standing* policy (what
axes exist, what each blast-radius tier requires), the contract is one change's declaration
against it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

DEFAULT_CONFIG_NAMES = ("greenbar.yaml", "greenbar.yml", ".greenbar.yaml")


@dataclass
class GreenbarConfig:
    axes: Dict[str, List[str]]      # profile -> [axis, ...]  (the RT-LQS analog, project-defined)
    tiers: Dict[str, dict]          # tier -> {gates: [...]}   (blast-radius ladder)
    gates: Dict[str, dict]          # gate -> {builtin|run|requires_file: ...}
    path: Path
    raw: dict


def find_config(start: Optional[Path] = None) -> Optional[Path]:
    start = (start or Path.cwd()).resolve()
    for d in [start, *start.parents]:
        for name in DEFAULT_CONFIG_NAMES:
            p = d / name
            if p.exists():
                return p
    return None


def load_config(path: Optional[str | Path] = None) -> GreenbarConfig:
    p = Path(path) if path else find_config()
    if not p or not p.exists():
        raise FileNotFoundError("no greenbar.yaml found (run `greenbar init`)")
    raw = yaml.safe_load(p.read_text()) or {}
    return GreenbarConfig(
        axes=raw.get("axes") or {},
        tiers=raw.get("tiers") or {},
        gates=raw.get("gates") or {},
        path=p,
        raw=raw,
    )
