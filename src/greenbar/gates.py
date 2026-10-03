"""The gate ladder — run a tier's required checks and aggregate pass/fail.

Three gate kinds keep v1 dependency-free and tool-agnostic:
  - ``builtin: contract``      → run Greenbar's own contract validator
  - ``run: "<shell command>"`` → any check that exits 0 on pass (ruff, mypy, pytest, semgrep, …)
  - ``requires_file: <path>``  → assert an artifact exists (e.g. a review-panel record; the
                                 review runner is a v2 plugin, but the *gate* that a record must
                                 exist is enforceable today)

A tier is a named list of gate names. ``run_tier`` returns one GateResult per gate; the CLI exits
non-zero if any required gate failed, which is what a CI branch-protection rule blocks on.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .config import GreenbarConfig
from .contract import load_contract, validate_contract
from .review import check_review_record

DEFAULT_RUN_TIMEOUT_S = 1800  # per `run:` gate; override with gate `timeout_s` or top-level `gate_timeout_s`


@dataclass
class GateResult:
    name: str
    ok: bool
    detail: str = ""


def _check_adr(spec: dict, contract: Optional[str]) -> "GateResult":
    """A deterministic design gate: an Architecture Decision Record must exist in ``dir`` and,
    when ``must_reference_contract`` is set, mention the contract's id — so every design-tier
    change leaves a decision trail. Degrades gracefully (clear failure, never a crash)."""
    adr_dir = Path(spec.get("dir", "docs/adr"))
    if not adr_dir.exists():
        return GateResult("adr", False, f"no ADR directory: {adr_dir} (add one and record the decision)")
    adrs = sorted(p for p in adr_dir.glob("**/*.md"))
    if not adrs:
        return GateResult("adr", False, f"no ADRs found under {adr_dir}")
    if spec.get("must_reference_contract") and contract:
        try:
            from .contract import load_contract
            meta, _ = load_contract(contract)
            cid = str(meta.get("id", "")).strip()
        except Exception:  # noqa: BLE001
            cid = ""
        if cid:
            hits = [p.name for p in adrs if cid in p.read_text(encoding="utf-8", errors="ignore")]
            if not hits:
                return GateResult("adr", False,
                                  f"no ADR under {adr_dir} references contract id {cid!r} — record the decision")
            return GateResult("adr", True, f"ADR references {cid}: {', '.join(hits)}")
    return GateResult("adr", True, f"{len(adrs)} ADR(s) present under {adr_dir}")


def run_gate(name: str, spec: dict, cfg: GreenbarConfig, contract: Optional[str]) -> GateResult:
    spec = spec or {}
    if spec.get("builtin") == "contract":
        if not contract:
            return GateResult(name, False, "no contract given (pass --contract or set gate.contract)")
        try:
            meta, _ = load_contract(contract)
        except Exception as exc:  # noqa: BLE001 — surface parse errors as a gate failure
            return GateResult(name, False, f"contract parse error: {exc}")
        findings = validate_contract(meta, cfg.axes, tiers=list(cfg.tiers))
        errors = [x for x in findings if x.level == "error"]
        detail = "\n".join(f"    {x}" for x in findings) or "    ok"
        return GateResult(name, not errors, detail)

    if spec.get("builtin") == "adr":
        return _check_adr(spec, contract)

    if spec.get("builtin") == "review":
        record_path = spec.get("record", ".greenbar/review-record.json")
        ok, detail = check_review_record(
            contract, record_path, fail_on_rubber_stamp=bool(spec.get("fail_on_rubber_stamp"))
        )
        return GateResult(name, ok, detail)

    if "requires_file" in spec:
        target = spec["requires_file"]
        ok = Path(target).exists()
        return GateResult(name, ok, "found" if ok else f"missing required artifact: {target}")

    if "run" in spec:
        # a hung check must fail the gate, not hang CI or an agent's MCP call
        timeout_s = float(spec.get("timeout_s") or cfg.raw.get("gate_timeout_s") or DEFAULT_RUN_TIMEOUT_S)
        try:
            proc = subprocess.run(spec["run"], shell=True, capture_output=True, text=True,
                                  timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return GateResult(name, False, f"timed out after {timeout_s:g}s: {spec['run']}")
        detail = (proc.stdout + proc.stderr).strip()
        return GateResult(name, proc.returncode == 0, detail[-4000:])

    return GateResult(name, False, f"gate {name!r} defines none of builtin/run/requires_file")


def run_tier(tier: str, cfg: GreenbarConfig, contract: Optional[str] = None) -> List[GateResult]:
    t = cfg.tiers.get(tier)
    if t is None:
        raise KeyError(f"unknown tier {tier!r}; known tiers: {', '.join(cfg.tiers) or '(none)'}")
    gate_names = (t or {}).get("gates") or []
    if not gate_names:
        # fail-closed: a tier that checks nothing must not read as a green build
        return [GateResult("tier", False, f"tier {tier!r} defines no gates — give it at least one")]
    results: List[GateResult] = []
    for gate_name in gate_names:
        spec = cfg.gates.get(gate_name)
        if spec is None:
            results.append(GateResult(gate_name, False, "gate is not defined under gates: in greenbar.yaml"))
            continue
        results.append(run_gate(gate_name, spec, cfg, contract))
    return results


def gate_event(tier: str, contract: Optional[str], results: List[GateResult],
               commit: Optional[str]) -> dict:
    """The history record for one gate run — the unit `report` and `accountability` count."""
    return {
        "kind": "gate", "tier": tier, "contract": contract, "ok": all(r.ok for r in results),
        "commit": commit,   # links a later revert of this commit back to its gate result
        "gates": [{"name": r.name, "ok": r.ok} for r in results],
    }
