"""Auto blast-radius classification — infer a change's tier from its diff.

So rigor scales to impact without a human deciding: a docs typo runs the `trivial` gates, a
migration/auth change runs `critical`. Rules are evaluated top-to-bottom, **first match wins**;
if none match, the configured `default`. A rule with no conditions never matches (guards against an
accidental catch-all).

Config (in greenbar.yaml):

    classify:
      default: scoped
      rules:
        - { tier: critical, any_path: ["**/migrations/**", "**/auth/**", "**/*secret*", "**/consent*"] }
        - { tier: critical, min_files: 30 }
        - { tier: critical, min_lines: 800 }
        - { tier: trivial,  only_paths: ["**/*.md", "docs/**"] }
        - { tier: trivial,  max_files: 1, max_lines: 10 }
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

_CONDITION_KEYS = ("any_path", "only_paths", "min_files", "max_files", "min_lines", "max_lines")


def glob_to_re(pattern: str) -> "re.Pattern[str]":
    """Translate a path glob to a regex. `**/` = any dirs (incl. none), `**` = anything,
    `*` = within one segment, `?` = one non-slash char."""
    out: List[str] = []
    i, n = 0, len(pattern)
    while i < n:
        if pattern[i : i + 3] == "**/":
            out.append("(?:.*/)?"); i += 3
        elif pattern[i : i + 2] == "**":
            out.append(".*"); i += 2
        elif pattern[i] == "*":
            out.append("[^/]*"); i += 1
        elif pattern[i] == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(pattern[i])); i += 1
    return re.compile("^" + "".join(out) + "$")


@dataclass
class DiffStat:
    files: List[str]
    added: int
    removed: int

    @property
    def total_lines(self) -> int:
        return self.added + self.removed


def parse_numstat(text: str) -> DiffStat:
    """Parse `git diff --numstat` output: `<added>\\t<removed>\\t<path>` (binary → `-`)."""
    files: List[str] = []
    added = removed = 0
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2]:
            a = 0 if parts[0] in ("-", "") else int(parts[0])
            d = 0 if parts[1] in ("-", "") else int(parts[1])
            added += a
            removed += d
            files.append(parts[2])
    return DiffStat(files, added, removed)


def parse_unified_diff(text: str) -> DiffStat:
    """Extract files + added/removed line counts from a unified diff (for `--diff <file>`)."""
    files: List[str] = []
    added = removed = 0
    for line in text.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path and path != "/dev/null":
                files.append(path)
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return DiffStat(files, added, removed)


def git_numstat(base: Optional[str] = None) -> DiffStat:
    cmd = ["git", "diff", "--numstat"] + ([f"{base}...HEAD"] if base else ["HEAD"])
    try:
        return parse_numstat(subprocess.run(cmd, capture_output=True, text=True).stdout)
    except Exception:  # noqa: BLE001 — no git / not a repo → empty
        return DiffStat([], 0, 0)


def _match_any(globs, files) -> bool:
    pats = [glob_to_re(g) for g in globs]
    return any(p.match(f) for f in files for p in pats)


def _match_all(globs, files) -> bool:
    if not files:
        return False
    pats = [glob_to_re(g) for g in globs]
    return all(any(p.match(f) for p in pats) for f in files)


def _rule_matches(rule: dict, stat: DiffStat) -> bool:
    if not any(k in rule for k in _CONDITION_KEYS):
        return False  # a rule with no conditions is NOT a catch-all
    if "any_path" in rule and not _match_any(rule["any_path"], stat.files):
        return False
    if "only_paths" in rule and not _match_all(rule["only_paths"], stat.files):
        return False
    nf = len(stat.files)
    if "min_files" in rule and nf < rule["min_files"]:
        return False
    if "max_files" in rule and nf > rule["max_files"]:
        return False
    if "min_lines" in rule and stat.total_lines < rule["min_lines"]:
        return False
    if "max_lines" in rule and stat.total_lines > rule["max_lines"]:
        return False
    return True


def classify(stat: DiffStat, classify_cfg: dict) -> Tuple[str, str]:
    """Return (tier, reason). First matching rule wins; else the default."""
    default = classify_cfg.get("default", "scoped")
    for idx, rule in enumerate(classify_cfg.get("rules") or []):
        tier = rule.get("tier")
        if tier and _rule_matches(rule, stat):
            conds = {k: rule[k] for k in _CONDITION_KEYS if k in rule}
            return tier, f"rule[{idx}] matched {conds}"
    return default, f"no rule matched → default ({default})"
