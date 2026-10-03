"""`greenbar draft` — scaffold a lint-clean contract from a PRD.

The contract is the main adoption friction; `draft` removes the blank page. It works with NO LLM by
default (heuristic parsing of the PRD's goal / non-goals / requirement bullets), and optionally pipes
the PRD + the schema to any model CLI (`--with "<cmd>"`) — the same provider-agnostic pattern as the
review lenses — falling back to the deterministic draft if that fails.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml


@dataclass
class ParsedPRD:
    title: Optional[str] = None
    goal: Optional[str] = None
    non_goals: List[str] = field(default_factory=list)
    acceptance: List[str] = field(default_factory=list)


_GOAL_LABELS = ("requirement", "goal", "objective", "problem")
_NONGOAL_LABELS = ("out of scope", "non-goal", "non goal", "not in scope", "out-of-scope")
_ACCEPT_LABELS = ("acceptance", "requirement", "criteria", "must", "behaviou", "spec")


def _strip_bullet(s: str) -> str:
    return re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", s).strip()


def _label_value(line: str, labels) -> Optional[str]:
    # matches "**Requirement:** value" / "Goal: value" / "- Out of scope: a, b"
    m = re.match(r"\s*(?:[-*+]\s*)?\**\s*([A-Za-z][A-Za-z /-]+?)\s*\**\s*[:：]\s*(.*)", line)
    if m and m.group(1).strip().lower() in labels:
        # strip trailing markdown emphasis that closed after the colon (e.g. "**Label:** value")
        return m.group(2).strip().strip("*").strip()
    return None


def parse_prd(text: str) -> ParsedPRD:
    lines = text.splitlines()
    p = ParsedPRD()

    for l in lines:
        if l.startswith("# "):
            p.title = l[2:].strip()
            break

    # goal: a labelled line, else the title, else first non-empty non-heading line
    for l in lines:
        v = _label_value(l, _GOAL_LABELS)
        if v:
            p.goal = v
            break
    if not p.goal:
        p.goal = p.title
    if not p.goal:
        for l in lines:
            if l.strip() and not l.startswith("#"):
                p.goal = l.strip()
                break

    # section scan for non-goals / acceptance (heading- or label-driven)
    section = None
    for raw in lines:
        line = raw.rstrip()
        low = line.lower()
        # inline "Out of scope: a, b, c"
        v = _label_value(line, _NONGOAL_LABELS)
        if v is not None:
            p.non_goals.extend(x.strip() for x in re.split(r"[;,]", v) if x.strip())
            section = None
            continue
        # heading transitions
        if line.startswith("#") or re.match(r"\s*\**[A-Za-z].*\**\s*[:：]\s*$", line):
            if any(k in low for k in _NONGOAL_LABELS):
                section = "non_goals"
            elif any(k in low for k in _ACCEPT_LABELS):
                section = "acceptance"
            else:
                section = None
            continue
        # bullets under a section
        if re.match(r"\s*(?:[-*+]|\d+[.)])\s+", line):
            item = _strip_bullet(line)
            if section == "non_goals":
                p.non_goals.append(item)
            elif section == "acceptance":
                p.acceptance.append(item)
            elif re.search(r"\b(must|shall|should|returns?)\b", low):
                p.acceptance.append(item)  # a requirement-shaped bullet anywhere

    # de-dup, keep order
    p.non_goals = list(dict.fromkeys(p.non_goals))
    p.acceptance = list(dict.fromkeys(p.acceptance))
    return p


def build_contract(parsed: ParsedPRD, contract_id: str, tier: str,
                   axis_catalog: Dict[str, List[str]], prd_body: str = "") -> str:
    profile = next(iter(axis_catalog), "C")
    axes = axis_catalog.get(profile, ["correctness", "reasonableness"])

    acceptance = [{"id": f"A{i + 1}", "must": a} for i, a in enumerate(parsed.acceptance[:8])]
    if not acceptance:
        acceptance = [{"id": "A1", "must": "TODO — a binary, verifiable criterion from the PRD"}]

    fm: Dict = {
        "id": contract_id,
        "goal": parsed.goal or "TODO — one line: what · measurable bar · constraint",
        "tier": tier,
        "non_goals": parsed.non_goals or ["TODO — what this deliberately does not do"],
        "acceptance": acceptance,
        "quality_axes": {
            "profiles": [profile],
            "axes": {f"{a}@{profile}": {"state": "asserted"} for a in axes},
            "kpis": [
                {"id": f"K{i + 1}", "axis": a, "profile": profile, "must_have": True,
                 "target": "TODO — a behavioral target (error-rate / effect-size / equality)"}
                for i, a in enumerate(axes)
            ],
        },
        "hitl": ["merge to main"],
    }
    front = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False, allow_unicode=True).strip()
    body = (
        f"# {contract_id}\n\n"
        "**This is a DRAFT** scaffolded by `greenbar draft` — replace every `TODO`, tighten the\n"
        "acceptance criteria to binary form, then run `greenbar lint`.\n\n"
        "## From the PRD\n\n" + (prd_body.strip() or "(paste the PRD context here)")
    )
    return f"---\n{front}\n---\n\n{body}\n"


def draft_with_command(command: str, prd_text: str, contract_id: str, tier: str,
                       timeout_s: float = 120) -> Optional[str]:
    """Pipe the PRD + the schema to a model CLI; return its output, or None to fall back."""
    prompt = (
        "Fill this Greenbar contract from the PRD. Output ONLY the contract markdown (YAML "
        "frontmatter delimited by --- then a body), nothing else.\n\n"
        f"Required frontmatter keys: id (use {contract_id!r}), goal (one line: what · measurable "
        f"bar · constraint), tier (use {tier!r}), non_goals (list), acceptance (list of "
        "{id, must} where each 'must' is BINARY/verifiable), quality_axes (profiles + axes each "
        "asserted/deferred/n_a + kpis where every asserted axis has a must_have behavioral KPI), "
        "hitl (list).\n\n## PRD\n" + prd_text
    )
    try:
        proc = subprocess.run(command, shell=True, input=prompt, capture_output=True,
                              text=True, timeout=timeout_s)
    except Exception:  # noqa: BLE001
        return None
    out = (proc.stdout or "").strip()
    return out if (proc.returncode == 0 and "---" in out) else None
