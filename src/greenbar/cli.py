"""Greenbar CLI: init · lint · gate.

  greenbar init [path]                      scaffold greenbar.yaml + a contract template
  greenbar lint <contract> [--config C]     validate a contract (exit 1 on any error)
  greenbar gate <tier> [--contract C] [-v]  run the tier's gates (exit 1 if any fail)

The exit codes are the point: wire `greenbar gate <tier>` into CI + branch protection and a change
cannot merge unless its tier's gates are green.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import subprocess
from datetime import datetime, timezone

import yaml

from . import __version__
from .classify import DiffStat, classify, git_numstat, parse_unified_diff
from .config import load_config
from .contract import ContractError, load_contract, validate_contract
from .gates import gate_event, run_tier
from .history import current_commit, read_all_events, read_events, record_event, record_note
from .report import aggregate, format_report
from .review import plural, run_review

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


def _git_commits(limit: int = 2000):
    """Return [Commit(...)] from git log (sha, commit-time, subject, body); [] if not a git repo."""
    from .accountability import Commit
    fmt = "%H%x1f%ct%x1f%s%x1f%b"
    try:
        out = subprocess.run(
            ["git", "log", f"-n{limit}", "-z", f"--format={fmt}"], capture_output=True, text=True
        )
    except Exception:  # noqa: BLE001
        return []
    commits = []
    for rec in out.stdout.split("\x00"):
        if not rec.strip():
            continue
        parts = rec.split("\x1f")
        if len(parts) >= 4:
            try:
                commits.append(Commit(parts[0], int(parts[1]), parts[2], parts[3]))
            except ValueError:
                continue
    return commits


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "draft"


def _cmd_init(args) -> int:
    dest = Path(args.path or ".")
    dest.mkdir(parents=True, exist_ok=True)
    cfg = dest / "greenbar.yaml"
    if cfg.exists():
        print(f"greenbar: {cfg} already exists — leaving it")
    else:
        tmpl = _TEMPLATES / "greenbar.template.yaml"
        if getattr(args, "preset", None):
            ptmpl = _TEMPLATES / "presets" / f"{args.preset}.yaml"
            if ptmpl.exists():
                tmpl = ptmpl
            else:
                print(f"greenbar: no preset {args.preset!r} — using the generic template")
        cfg.write_text(tmpl.read_text())
        print(f"greenbar: wrote {cfg}" + (f" (preset: {args.preset})" if getattr(args, "preset", None) and tmpl != _TEMPLATES / 'greenbar.template.yaml' else ""))
    cdir = dest / "contracts"
    cdir.mkdir(exist_ok=True)
    example = cdir / "CONTRACT.example.md"
    if not example.exists():
        example.write_text((_TEMPLATES / "CONTRACT.template.md").read_text())
        print(f"greenbar: wrote {example}")
    # the architecture design-lens pack (referenced by the `design` tier in greenbar.yaml)
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
            print(f"greenbar: wrote {copied} design-lens rubric(s) into {ldir}/")
    gitignore = dest / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    if ".greenbar/" not in existing.split():
        sep = "" if not existing or existing.endswith("\n") else "\n"
        gitignore.write_text(existing + sep + ".greenbar/\n")
        print(f"greenbar: added .greenbar/ (local run state) to {gitignore}")
    for agent in getattr(args, "agent", None) or []:
        _install_agent_adapter(dest, agent)
    print("next: edit the contract, then `greenbar lint contracts/CONTRACT.example.md`")
    print("      let your agent call the gates mid-task:  claude mcp add greenbar -- greenbar mcp")
    if not getattr(args, "agent", None):
        print("      (add `--agent claude-code` or `--agent cursor` to install the agent instructions)")
    return 0


_AGENT_TARGETS = {
    # where each tool auto-loads project instructions
    "claude-code": (Path("adapters/claude-code/SKILL.md"), Path(".claude/skills/greenbar/SKILL.md")),
    "cursor": (Path("adapters/cursor/greenbar.rules.md"), Path(".cursor/rules/greenbar.mdc")),
}


def _install_agent_adapter(dest: Path, agent: str) -> None:
    src_rel, tgt_rel = _AGENT_TARGETS[agent]
    tgt = dest / tgt_rel
    if tgt.exists() or tgt.is_symlink():  # a dangling symlink would otherwise be written through
        print(f"greenbar: {tgt} already exists — leaving it")
        return
    body = (_TEMPLATES / src_rel).read_text()
    if agent == "cursor":
        # a Cursor project rule: frontmatter + the rules, minus the manual "paste this" line
        lines = [ln for ln in body.splitlines() if not ln.startswith("Paste into")]
        body = ("---\ndescription: Greenbar contract-first loop — author, lint and gate every "
                "non-trivial change\nalwaysApply: true\n---\n" + "\n".join(lines).strip() + "\n")
    tgt.parent.mkdir(parents=True, exist_ok=True)
    tgt.write_text(body)
    print(f"greenbar: wrote {tgt} ({agent} instructions)")


def _cmd_lint(args) -> int:
    cfg = load_config(args.config)
    try:
        meta, _ = load_contract(args.contract)
    except (ContractError, OSError, yaml.YAMLError) as exc:
        # a malformed contract is a lint failure with a clear message, never a traceback
        print(f"[error] C000: cannot parse {args.contract}: {exc}")
        print(f"\ngreenbar lint {args.contract}: 1 error(s), 0 warning(s)")
        return 1
    findings = validate_contract(meta, cfg.axes, tiers=list(cfg.tiers))
    for x in findings:
        print(x)
    errors = [x for x in findings if x.level == "error"]
    print(f"\ngreenbar lint {args.contract}: {len(errors)} error(s), "
          f"{len(findings) - len(errors)} warning(s)")
    return 1 if errors else 0


def _cmd_gate(args) -> int:
    cfg = load_config(args.config)
    tier = args.tier
    if args.auto or tier is None:
        tier, why = classify(_resolve_diff_stat(args), cfg.raw.get("classify") or {})
        print(f"greenbar: auto-classified tier = {tier}  ({why})")
    results = run_tier(tier, cfg, args.contract)
    failed = [r for r in results if not r.ok]
    for r in results:
        print(f"[{'PASS' if r.ok else 'FAIL'}] {r.name}")
        if (args.verbose or not r.ok) and r.detail:
            print("\n".join("    " + line for line in r.detail.splitlines()))
    print(f"\ngreenbar gate '{tier}': {len(results) - len(failed)}/{len(results)} passed")
    event = gate_event(tier, args.contract, results, current_commit())
    record_event(event)
    if args.notes and not record_note(event, event["commit"]):
        print("greenbar: could not write the git note (not a git repo, or no commit?)")
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
    print(f"\ngreenbar review: {s['verdict']} · {plural(m['lens_count'], 'lens', 'lenses')} · "
          f"{plural(m['finding_count'], 'finding')}"
          f"{' · ⚠ all-SIGN/zero-findings' if m['all_sign_no_findings'] else ''}  →  {args.out}")
    record_event({
        "kind": "review", "contract": args.contract, "verdict": s["verdict"],
        "lens_count": m["lens_count"], "finding_count": m["finding_count"],
        "all_sign_no_findings": m["all_sign_no_findings"],
    })
    return 1 if s["verdict"] in ("BLOCKED", "NO_LENSES") else 0


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
    events = read_events(args.history) if args.no_notes else read_all_events(args.history)
    agg = aggregate(events)
    if args.json:
        print(_json.dumps(agg, indent=2))
    else:
        print(format_report(agg))
    return 0


def _cmd_render(args) -> int:
    import json as _json

    from .render import render_pr_comment

    events = read_events(args.history)
    gate_event = next((e for e in reversed(events) if e.get("kind") == "gate"), None)

    paths = list(args.review or [])
    if not paths:
        for default in (".greenbar/review-record.json", ".greenbar/design-review.json"):
            if Path(default).exists():
                paths.append(default)
    reviews = []
    for p in paths:
        label = "Design review" if "design" in Path(p).name else "Code review"
        try:
            reviews.append((label, _json.loads(Path(p).read_text())))
        except Exception:  # noqa: BLE001
            pass

    md = render_pr_comment(gate_event, reviews)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md)
        print(f"greenbar: wrote {args.out}")
    else:
        print(md)
    return 0


def _cmd_accountability(args) -> int:
    import json as _json
    from dataclasses import asdict

    from .accountability import compute, format_report

    incidents = None
    if args.incidents:
        incidents = [l.strip().split()[0] for l in Path(args.incidents).read_text().splitlines()
                     if l.strip() and not l.strip().startswith("#")]
    events = read_events(args.history) if args.no_notes else read_all_events(args.history)
    rep = compute(events, _git_commits(), incidents=incidents,
                  window_days=args.window_days)
    if args.json:
        print(_json.dumps(asdict(rep), indent=2))
    else:
        print(format_report(rep))
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


def _cmd_draft(args) -> int:
    from .draft import build_contract, draft_with_command, parse_prd

    prd_text = Path(args.prd).read_text()
    cid = args.id or _slug(Path(args.prd).stem)
    tier = args.tier
    if tier is None:
        try:
            tier = (load_config(args.config).raw.get("classify") or {}).get("default", "scoped")
        except Exception:  # noqa: BLE001
            tier = "scoped"
    out = Path(args.out or f"contracts/{cid}.md")

    content = None
    if args.with_cmd:
        content = draft_with_command(args.with_cmd, prd_text, cid, tier)
        if content is None:
            print("greenbar: --with command failed or returned no contract → deterministic draft")
    if content is None:
        try:
            axes = load_config(args.config).axes or {"C": ["correctness", "reasonableness"]}
        except Exception:  # noqa: BLE001
            axes = {"C": ["correctness", "reasonableness"]}
        content = build_contract(parse_prd(prd_text), cid, tier, axes, prd_body=prd_text)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content)
    print(f"greenbar: wrote {out}")
    print(f"next: fill the TODOs, then `greenbar lint {out}`")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="greenbar", description="Contract-first, gate-enforced development framework."
    )
    p.add_argument("--version", action="version", version=f"greenbar {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="scaffold greenbar.yaml + a contract template")
    pi.add_argument("path", nargs="?", help="target directory (default: .)")
    pi.add_argument("--preset", help="stack preset for gates: python | node | go | rust")
    pi.add_argument("--agent", action="append", choices=sorted(_AGENT_TARGETS),
                    help="install agent instructions: claude-code | cursor (repeatable)")
    pi.set_defaults(func=_cmd_init)

    pd = sub.add_parser("draft", help="scaffold a contract from a PRD")
    pd.add_argument("prd", help="path to the PRD / issue markdown")
    pd.add_argument("--id", help="contract id (default: slug of the PRD filename)")
    pd.add_argument("--tier", help="tier (default: classify.default from greenbar.yaml)")
    pd.add_argument("--out", help="output path (default: contracts/<id>.md)")
    pd.add_argument("--with", dest="with_cmd", help="model CLI to draft with (else deterministic)")
    pd.add_argument("--config", help="path to greenbar.yaml")
    pd.set_defaults(func=_cmd_draft)

    pl = sub.add_parser("lint", help="validate a contract")
    pl.add_argument("contract")
    pl.add_argument("--config", help="path to greenbar.yaml (default: search upward)")
    pl.set_defaults(func=_cmd_lint)

    pg = sub.add_parser("gate", help="run a tier's gates")
    pg.add_argument("tier", nargs="?", help="tier to run (omit with --auto to classify from the diff)")
    pg.add_argument("--auto", action="store_true", help="infer the tier from the diff (classify)")
    pg.add_argument("--contract", help="contract for the builtin `contract` gate")
    pg.add_argument("--diff", help="diff file for --auto (default: `git diff HEAD`)")
    pg.add_argument("--diff-base", help="git ref to diff against for --auto")
    pg.add_argument("--config", help="path to greenbar.yaml")
    pg.add_argument("-v", "--verbose", action="store_true", help="print detail for passing gates too")
    pg.add_argument("--notes", action="store_true",
                    help="also record the result as a git note (refs/notes/greenbar) on the gated commit")
    pg.set_defaults(func=_cmd_gate)

    pc = sub.add_parser("classify", help="infer a change's tier from its diff")
    pc.add_argument("--diff", help="diff file (default: `git diff HEAD`)")
    pc.add_argument("--diff-base", help="git ref to diff against")
    pc.add_argument("--config", help="path to greenbar.yaml")
    pc.set_defaults(func=_cmd_classify)

    prep = sub.add_parser("report", help="aggregate the gate/review history")
    prep.add_argument("--history", default=".greenbar/history.jsonl")
    prep.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    prep.add_argument("--no-notes", action="store_true", help="ignore git-notes history (local file only)")
    prep.set_defaults(func=_cmd_report)

    prn = sub.add_parser("render", help="render the latest gate + review artifacts as a Markdown PR comment")
    prn.add_argument("--history", default=".greenbar/history.jsonl")
    prn.add_argument("--review", action="append", help="review record json (repeatable; default: auto-detect)")
    prn.add_argument("--out", help="write to a file instead of stdout")
    prn.set_defaults(func=_cmd_render)

    pa = sub.add_parser("accountability", help="defect-escape rate: gate-passed changes later reverted")
    pa.add_argument("--history", default=".greenbar/history.jsonl")
    pa.add_argument("--incidents", help="file of commit SHAs (one per line) known to be defective")
    pa.add_argument("--window-days", type=float, help="only attribute a revert within N days of merge")
    pa.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    pa.add_argument("--no-notes", action="store_true", help="ignore git-notes history (local file only)")
    pa.set_defaults(func=_cmd_accountability)

    pr = sub.add_parser("review", help="run the configured lenses and write a review record")
    pr.add_argument("--contract", help="contract under review (its hash pins record freshness)")
    pr.add_argument("--diff", help="path to a diff file (default: `git diff HEAD`)")
    pr.add_argument("--diff-base", help="git ref to diff against (`<base>...HEAD`)")
    pr.add_argument("--out", default=".greenbar/review-record.json", help="where to write the record")
    pr.add_argument("--group", help="only run lenses with this group (e.g. 'design')")
    pr.add_argument("--config", help="path to greenbar.yaml")
    pr.set_defaults(func=_cmd_review)

    po = sub.add_parser("orient", help="emit a token-bounded code map (focus with --diff)")
    po.add_argument("--path", help="repo root to map (default: .)")
    po.add_argument("--diff", help="diff file — bias the map toward its changed files")
    po.add_argument("--diff-base", help="git ref to diff against for the focus")
    po.add_argument("--budget", type=int, default=1200, help="approx token budget for the map")
    po.add_argument("--top", type=int, default=40, help="max symbols in --json output")
    po.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    po.set_defaults(func=_cmd_orient)

    pm = sub.add_parser("mcp", help="run the MCP server over stdio (agent-native)")
    pm.set_defaults(func=_cmd_mcp)
    return p


def _cmd_mcp(args) -> int:
    from .mcp_server import serve
    return serve()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
