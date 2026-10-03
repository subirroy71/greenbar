"""Parse and validate a Trellis contract — the machine-checkable `/goals`.

A contract is a Markdown file with a YAML frontmatter block (the structured, lintable part) and a
prose body (context, method, notes). The validator enforces the rules that, in an advisory
workflow, are checked only by a human reading the doc — most importantly: **an asserted quality
axis must carry a behavioral must-have KPI, or be explicitly deferred / n_a.** That single rule is
what turns "we said we'd cover accuracy" into "the pipeline proves we declared how."
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import yaml


class ContractError(Exception):
    """Raised when a contract cannot even be parsed (malformed frontmatter)."""


@dataclass
class Finding:
    level: str  # "error" | "warn"
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.code}: {self.message}"


_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
_VALID_STATES = {"asserted", "deferred", "n_a"}
# Scaffold markers (`trellis draft` emits "TODO — ..."): a field that still *starts* with one hasn't
# been written yet, so it must not satisfy the gate. Anchored, so prose that merely mentions a
# marker ("lint rejects TODO targets") is not a false positive.
_PLACEHOLDER = re.compile(r"^\W*(TODO|TBD|FIXME)\b", re.IGNORECASE)


def parse_contract(text: str) -> Tuple[dict, str]:
    """Split a contract into (frontmatter dict, prose body)."""
    m = _FRONTMATTER.match(text)
    if not m:
        raise ContractError("contract must begin with a YAML frontmatter block delimited by '---'")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ContractError("frontmatter must be a YAML mapping")
    return meta, m.group(2)


def load_contract(path: str | Path) -> Tuple[dict, str]:
    return parse_contract(Path(path).read_text())


def _placeholders(meta: dict) -> Iterable[Tuple[str, str]]:
    """Yield (field-path, text) for every human-authored string that is still a placeholder."""
    def walk(node, path: str):
        if isinstance(node, str):
            if _PLACEHOLDER.search(node):
                yield path, node
        elif isinstance(node, dict):
            for k, v in node.items():
                yield from walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from walk(v, f"{path}[{i}]")

    for key in ("goal", "non_goals", "acceptance"):
        yield from walk(meta.get(key), key)
    qa = meta.get("quality_axes") or {}
    if isinstance(qa, dict):
        yield from walk(qa.get("kpis"), "quality_axes.kpis")
        yield from walk(qa.get("axes"), "quality_axes.axes")


def validate_contract(meta: dict, axis_catalog: Dict[str, List[str]],
                      tiers: Optional[Iterable[str]] = None) -> List[Finding]:
    """Validate a contract's frontmatter against the project's axis catalog.

    ``axis_catalog`` maps a profile letter (e.g. "C", "D") to the list of quality axes that apply
    to it (e.g. C -> [accuracy, reasonableness, latency]). Every axis of every declared profile
    must be accounted for. ``tiers`` (the project's tier names) makes an undeclared ``tier`` an
    error; omit it to skip that check. Errors fail the build; warnings don't.
    """
    findings: List[Finding] = []

    def err(code: str, msg: str) -> None:
        findings.append(Finding("error", code, msg))

    def warn(code: str, msg: str) -> None:
        findings.append(Finding("warn", code, msg))

    # 1 — required top-level fields
    for key in ("id", "goal", "tier", "acceptance", "quality_axes"):
        if not meta.get(key):
            err("C001", f"missing required field: {key!r}")
    tier = meta.get("tier")
    if tiers is not None and tier and str(tier) not in set(tiers):
        err("C013", f"tier {tier!r} is not defined in trellis.yaml (known: {', '.join(tiers) or 'none'})")
    for path, text in _placeholders(meta):
        err("C012", f"{path} is still a placeholder ({text[:60]!r}) — write the real content")
    if not meta.get("non_goals"):
        warn("C010", "no non_goals declared — scope creep is easier without an explicit out-list")

    # 2 — acceptance criteria must be binary + identified
    acc = meta.get("acceptance")
    if acc is not None:
        if not isinstance(acc, list) or not acc:
            err("C002", "acceptance must be a non-empty list of binary, verifiable criteria")
        else:
            for i, a in enumerate(acc):
                if not isinstance(a, dict) or not a.get("id") or not a.get("must"):
                    err("C003", f"acceptance[{i}] needs an 'id' and a 'must' (binary, verifiable) statement")

    # 3-7 — quality axes: every profile-applicable axis accounted; asserted ⇒ behavioral KPI
    qa = meta.get("quality_axes") or {}
    profiles = qa.get("profiles") or []
    axes = qa.get("axes") or {}
    kpis = qa.get("kpis") or []
    if not profiles:
        err("C004", "quality_axes.profiles must be non-empty")

    musthave: set[tuple[str, str]] = set()
    for k in kpis:
        if isinstance(k, dict) and k.get("must_have"):
            if not str(k.get("target") or "").strip():
                err("C014", f"must_have KPI {k.get('id', '?')!r} has no target — a KPI without a "
                            f"behavioral target proves nothing")
                continue
            musthave.add((str(k.get("axis")), str(k.get("profile"))))

    for prof in profiles:
        catalog = axis_catalog.get(str(prof))
        if catalog is None:
            err("C005", f"profile {prof!r} has no axis catalog (add axes.{prof} to trellis.yaml)")
            continue
        for axis in catalog:
            key = f"{axis}@{prof}"
            spec = axes.get(key)
            if spec is None:
                err("C006", f"axis '{axis}' for profile {prof} is unaccounted — "
                            f"declare {key} as asserted / deferred / n_a")
                continue
            state = (spec or {}).get("state")
            if state not in _VALID_STATES:
                err("C007", f"{key} has invalid state {state!r} (asserted | deferred | n_a)")
                continue
            if state == "asserted" and (axis, str(prof)) not in musthave:
                err("C008", f"{key} is asserted but has no must_have KPI — back it with a behavioral "
                            f"KPI or defer it (an axis asserted in name only is worse than deferred)")
            if state == "deferred" and not (spec or {}).get("deferred_to"):
                err("C009", f"{key} is deferred but names no deferred_to target")
            if state == "n_a" and not (spec or {}).get("signoff"):
                err("C011", f"{key} is n_a but carries no signoff (who + when authorised the exemption)")

    return findings
