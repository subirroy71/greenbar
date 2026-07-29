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

from . import __version__
from .config import load_config
from .contract import load_contract, validate_contract
from .gates import run_tier

_TEMPLATES = Path(__file__).parent / "templates"


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
    results = run_tier(args.tier, cfg, args.contract)
    failed = [r for r in results if not r.ok]
    for r in results:
        print(f"[{'PASS' if r.ok else 'FAIL'}] {r.name}")
        if (args.verbose or not r.ok) and r.detail:
            print("\n".join("    " + line for line in r.detail.splitlines()))
    print(f"\ntrellis gate '{args.tier}': {len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


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
    pg.add_argument("tier")
    pg.add_argument("--contract", help="contract for the builtin `contract` gate")
    pg.add_argument("--config", help="path to trellis.yaml")
    pg.add_argument("-v", "--verbose", action="store_true", help="print detail for passing gates too")
    pg.set_defaults(func=_cmd_gate)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
