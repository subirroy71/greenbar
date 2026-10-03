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

import os
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


_BRACE_RENAME = re.compile(r"^(.*)\{(.*) => (.*)\}(.*)$")


def _rename_paths(path: str) -> List[str]:
    """Expand numstat rename notation to BOTH paths — a code file renamed to `.md` must still count
    as code. Handles `old => new` and `pre/{old => new}/post`."""
    m = _BRACE_RENAME.match(path)
    if m:
        pre, old, new, post = m.groups()
        return [re.sub(r"//+", "/", f"{pre}{old}{post}"), re.sub(r"//+", "/", f"{pre}{new}{post}")]
    if " => " in path:
        old, new = path.split(" => ", 1)
        return [old, new]
    return [path]


def _add(files: List[str], path: str) -> None:
    if path and path != "/dev/null" and path not in files:
        files.append(path)


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
            for path in _rename_paths(parts[2]):
                _add(files, path)
    return DiffStat(files, added, removed)


def parse_unified_diff(text: str) -> DiffStat:
    """Extract files + added/removed line counts from a unified diff (for `--diff <file>`).

    Old paths count too (`--- a/…`, `rename from …`): deleting or renaming a code file is a code
    change, even if the only new path is a doc."""
    files: List[str] = []
    added = removed = 0
    # A hunk's @@ header says how many old/new lines follow; counting them down tells us exactly
    # where the hunk ends, so a removed "-- sql comment" is never read as a header and the next
    # file's headers are never read as content — with or without `diff --git` lines.
    old_left = new_left = 0
    for line in text.splitlines():
        if old_left > 0 or new_left > 0:
            if line.startswith("\\"):
                continue  # "\ No newline at end of file"
            if line.startswith("+"):
                added += 1
                new_left -= 1
            elif line.startswith("-"):
                removed += 1
                old_left -= 1
            else:
                old_left -= 1
                new_left -= 1
            continue
        hunk = re.match(r"@@ (-\d+(?:,(\d+))? )?\+\d+(?:,(\d+))? @@", line)
        if hunk:
            # an omitted count means 1; an omitted old range (`@@ +1 @@`) means no old lines
            old_left = 0 if hunk.group(1) is None else int(hunk.group(2) or 1)
            new_left = int(hunk.group(3) or 1)
        elif line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            if m:  # covers empty added/deleted files, which carry no ---/+++ lines
                _add(files, m.group(1))
                _add(files, m.group(2))
        elif line.startswith("+++ ") or line.startswith("--- "):
            path = line[4:].strip().split("\t")[0]
            if path[:2] in ("a/", "b/"):
                path = path[2:]
            _add(files, path)
        elif line.startswith("rename from ") or line.startswith("rename to "):
            _add(files, line.split(" ", 2)[2].strip())
    return DiffStat(files, added, removed)


def git_numstat(base: Optional[str] = None) -> DiffStat:
    # --no-renames: a rename is reported as delete + add, so both the old and new path are seen
    # core.quotepath=off: non-ASCII paths (docs/café.md) arrive unquoted, so globs match them
    cmd = (["git", "-c", "core.quotepath=off", "diff", "--numstat", "--no-renames"]
           + ([f"{base}...HEAD"] if base else ["HEAD"]))
    try:
        stat = parse_numstat(subprocess.run(cmd, capture_output=True, text=True).stdout)
    except Exception:  # noqa: BLE001 — no git / not a repo → empty
        return DiffStat([], 0, 0)
    if not base:
        # the working tree also holds untracked new files — a new code file beside a doc edit is a
        # code change. (A base..HEAD range only contains committed files, so CI needs no extra.)
        # Listed from the repo top so a subdirectory cwd can't hide untracked files elsewhere.
        try:
            top = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                 capture_output=True, text=True).stdout.strip()
            out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "--others",
                                  "--exclude-standard"], capture_output=True, text=True,
                                 cwd=top or None).stdout
        except Exception:  # noqa: BLE001
            top, out = "", ""
        for path in out.splitlines():
            if path.startswith(".greenbar/"):
                continue  # Greenbar's own local state is never part of the change
            if path.strip() and path not in stat.files:
                stat.files.append(path)
                try:
                    with open(os.path.join(top, path) if top else path, "rb") as fh:
                        stat.added += sum(1 for _ in fh)
                except OSError:
                    pass
    return stat


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
