"""Trellis CLI: init · lint · gate.

  trellis init [path]                      scaffold trellis.yaml + a contract template
  trellis lint <contract> [--config C]     validate a contract (exit 1 on any error)
  trellis gate <tier> [--contract C] [-v]  run the tier's gates (exit 1 if any fail)

The exit codes are the point: wire `trellis gate <tier>` into CI + branch protection and a change
cannot merge unless its tier's gates are green.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import subprocess
from datetime import datetime, timezone

from . import __version__
from .classify import DiffStat, classify, git_numstat, parse_unified_diff
from .config import load_config
from .contract import load_contract, validate_contract
from .gates import run_tier
from .history import read_events, record_event
from .report import aggregate, format_report
from .review import run_review

_TEMPLATES = Path(__file__).parent / "templates"


def _resolve_diff(args) -> str:
    if getattr(args, "diff", None):
        return Path(args.diff).read_text()
    base = getattr(args, "diff_base", None)
    cmd = ["git", "diff", f"{base}...HEAD"] if base else ["git", "diff", "HEAD"]
    try:
        return subprocess.run(cmd, capture_output=True, text=True).stdout
    except Exception:  # noqa: BLE001 — no git / not a repo → empty diff
        return ""


def _resolve_diff_stat(args) -> DiffStat:
    if getattr(args, "diff", None):
        return parse_unified_diff(Path(args.diff).read_text())
    return git_numstat(getattr(args, "diff_base", None))


def _cmd_init(args) -> int:
    dest = Path(args.path or ".")
    dest.mkdir(parents=True, exist_ok=True)
    cfg = dest / "trellis.yaml"
    if cfg.exists():
        print(f"trellis: {cfg} already exists — leaving it")
    else:
        cfg.write_text((_TEMPLATES / "trellis.template.yaml").read_text())
        print(f"trellis: wrote {cfg}")
    cdir = dest / "contracts"
    cdir.mkdir(exist_ok=True)
    example = cdir / "CONTRACT.example.md"
    if not example.exists():
        example.write_text((_TEMPLATES / "CONTRACT.template.md").read_text())
        print(f"trellis: wrote {example}")
    # the architecture design-lens pack (referenced by the `design` tier in trellis.yaml)
    src_lenses = _TEMPLATES / "lenses"
    if src_lenses.exists():
        ldir = dest / "lenses"
        ldir.mkdir(exist_ok=True)
        copied = 0
        for f in sorted(src_lenses.glob("*.md")):
            tgt = ldir / f.name
            if not tgt.exists():
                tgt.write_text(f.read_text())
                copied += 1
        if copied:
            print(f"trellis: wrote {copied} design-lens rubric(s) into {ldir}/")
    print("next: edit the contract, then `trellis lint contracts/CONTRACT.example.md`")
    return 0


def _cmd_lint(args) -> int:
    cfg = load_config(args.config)
    meta, _ = load_contract(args.contract)
    findings = validate_contract(meta, cfg.axes)
    for x in findings:
        print(x)
    errors = [x for x in findings if x.level == "error"]
    print(f"\ntrellis lint {args.contract}: {len(errors)} error(s), "
          f"{len(findings) - len(errors)} warning(s)")
    return 1 if errors else 0


def _cmd_gate(args) -> int:
    cfg = load_config(args.config)
    tier = args.tier
    if args.auto or tier is None:
        tier, why = classify(_resolve_diff_stat(args), cfg.raw.get("classify") or {})
        print(f"trellis: auto-classified tier = {tier}  ({why})")
    results = run_tier(tier, cfg, args.contract)
    failed = [r for r in results if not r.ok]
    for r in results:
        print(f"[{'PASS' if r.ok else 'FAIL'}] {r.name}")
        if (args.verbose or not r.ok) and r.detail:
            print("\n".join("    " + line for line in r.detail.splitlines()))
    print(f"\ntrellis gate '{tier}': {len(results) - len(failed)}/{len(results)} passed")
    record_event({
        "kind": "gate", "tier": tier, "contract": args.contract, "ok": not failed,
        "gates": [{"name": r.name, "ok": r.ok} for r in results],
    })
    return 1 if failed else 0


def _cmd_review(args) -> int:
    cfg = load_config(args.config)
    diff = _resolve_diff(args)
    now = datetime.now(timezone.utc).isoformat()
    rec = run_review(args.contract, cfg.raw, diff, now=now, out_path=args.out, group=args.group)
    for lens in rec["lenses"]:
        line = f"[{lens['verdict']:16}] {lens['name']}"
        if lens.get("error"):
            line += f"  ({lens['error']})"
        print(line)
        for f in lens.get("findings", []):
            print(f"    - {f}")
    m, s = rec["metrics"], rec["summary"]
    print(f"\ntrellis review: {s['verdict']} · {m['lens_count']} lenses · {m['finding_count']} findings"
          f"{' · ⚠ all-SIGN/zero-findings' if m['all_sign_no_findings'] else ''}  →  {args.out}")
    record_event({
        "kind": "review", "contract": args.contract, "verdict": s["verdict"],
        "lens_count": m["lens_count"], "finding_count": m["finding_count"],
        "all_sign_no_findings": m["all_sign_no_findings"],
    })
    return 1 if s["verdict"] == "BLOCKED" else 0


def _cmd_classify(args) -> int:
    cfg = load_config(args.config)
    stat = _resolve_diff_stat(args)
    tier, why = classify(stat, cfg.raw.get("classify") or {})
    print(f"tier: {tier}")
    print(f"  files={len(stat.files)} lines={stat.total_lines} (+{stat.added}/-{stat.removed})")
    print(f"  {why}")
    return 0


def _cmd_report(args) -> int:
    import json as _json
    agg = aggregate(read_events(args.history))
    if args.json:
        print(_json.dumps(agg, indent=2))
    else:
        print(format_report(agg))
    return 0


def _cmd_orient(args) -> int:
    import json as _json

    from .orient import build_graph, rank_symbols, render_map

    g = build_graph(args.path or ".")
    focus = None
    if args.diff or args.diff_base:
        focus = set(_resolve_diff_stat(args).files)
    ranked = rank_symbols(g, focus_files=focus)
    if args.json:
        top = [
            {"name": s.name, "kind": s.kind, "file": s.file, "line": s.line,
             "signature": s.signature, "score": round(score, 6)}
            for s, score in ranked[: args.top or 40]
        ]
        print(_json.dumps({"symbols": len(g.symbols), "focus_files": sorted(focus) if focus else [],
                           "top": top}, indent=2))
    else:
        if focus:
            print(f"# orientation for {len(focus)} changed file(s) · {len(g.symbols)} symbols in graph\n")
        else:
            print(f"# repo map · {len(g.symbols)} symbols\n")
        print(render_map(ranked, budget_tokens=args.budget))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="trellis", description="Contract-first, gate-enforced development framework."
    )
    p.add_argument("--version", action="version", version=f"trellis {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="scaffold trellis.yaml + a contract template")
    pi.add_argument("path", nargs="?", help="target directory (default: .)")
    pi.set_defaults(func=_cmd_init)

    pl = sub.add_parser("lint", help="validate a contract")
    pl.add_argument("contract")
    pl.add_argument("--config", help="path to trellis.yaml (default: search upward)")
    pl.set_defaults(func=_cmd_lint)

    pg = sub.add_parser("gate", help="run a tier's gates")
    pg.add_argument("tier", nargs="?", help="tier to run (omit with --auto to classify from the diff)")
    pg.add_argument("--auto", action="store_true", help="infer the tier from the diff (classify)")
    pg.add_argument("--contract", help="contract for the builtin `contract` gate")
    pg.add_argument("--diff", help="diff file for --auto (default: `git diff HEAD`)")
    pg.add_argument("--diff-base", help="git ref to diff against for --auto")
    pg.add_argument("--config", help="path to trellis.yaml")
    pg.add_argument("-v", "--verbose", action="store_true", help="print detail for passing gates too")
    pg.set_defaults(func=_cmd_gate)

    pc = sub.add_parser("classify", help="infer a change's tier from its diff")
    pc.add_argument("--diff", help="diff file (default: `git diff HEAD`)")
    pc.add_argument("--diff-base", help="git ref to diff against")
    pc.add_argument("--config", help="path to trellis.yaml")
    pc.set_defaults(func=_cmd_classify)

    prep = sub.add_parser("report", help="aggregate the gate/review history")
    prep.add_argument("--history", default=".trellis/history.jsonl")
    prep.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    prep.set_defaults(func=_cmd_report)

    pr = sub.add_parser("review", help="run the configured lenses and write a review record")
    pr.add_argument("--contract", help="contract under review (its hash pins record freshness)")
    pr.add_argument("--diff", help="path to a diff file (default: `git diff HEAD`)")
    pr.add_argument("--diff-base", help="git ref to diff against (`<base>...HEAD`)")
    pr.add_argument("--out", default=".trellis/review-record.json", help="where to write the record")
    pr.add_argument("--group", help="only run lenses with this group (e.g. 'design')")
    pr.add_argument("--config", help="path to trellis.yaml")
    pr.set_defaults(func=_cmd_review)

    po = sub.add_parser("orient", help="emit a token-bounded code map (focus with --diff)")
    po.add_argument("--path", help="repo root to map (default: .)")
    po.add_argument("--diff", help="diff file — bias the map toward its changed files")
    po.add_argument("--diff-base", help="git ref to diff against for the focus")
    po.add_argument("--budget", type=int, default=1200, help="approx token budget for the map")
    po.add_argument("--top", type=int, default=40, help="max symbols in --json output")
    po.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    po.set_defaults(func=_cmd_orient)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
