#!/usr/bin/env python3
"""Prepare a Google NotebookLM-ready video for the Trellis project.

NotebookLM has **no public API** — you upload sources in the web UI and click "Generate".
So this script automates the part that *can* be automated:

  1. assembles the repo's story into ONE clean source document (the "source pack"),
  2. writes an audience-tuned steering prompt (NotebookLM's Video/Audio Overview takes a
     free-text customization instruction), and
  3. writes a step-by-step guide + a narration beat sheet (a human-writable fallback script).

You then: open notebooklm.google.com -> new notebook -> upload the source pack ->
Video (or Audio) Overview -> "Customize" -> paste the prompt -> Generate.

Stdlib only. Re-run with different flags to retarget the video.

    python scripts/notebooklm/prepare_video.py --audience developers --format video --minutes 4
"""
from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # scripts/notebooklm/ -> repo root

# (path, why-it-matters) — order = narrative order in the pack. Missing files are skipped.
SOURCES = [
    ("README.md", "What Trellis is: the problem, the pitch, the features, how to use it."),
    ("CHANGELOG.md", "How it evolved v0.1 -> v0.10 — the capability arc."),
    ("contracts/CONTRACT.md", "A real contract — the core artifact the whole framework turns on."),
    ("contracts/mcp-server.md", "A second contract, showing the machine-checkable shape (goal/acceptance/axes)."),
]

AUDIENCES = {
    "developers": {
        "who": "a senior software engineer evaluating dev-governance and AI-coding tooling",
        "angle": (
            "Lead with the failure mode they recognize: 'smart operator + AI coding tool' produces good "
            "work ad hoc, but it isn't reproducible and it pushes quality defects into review instead of "
            "surfacing them at authoring. Then show how Trellis makes rigor mechanical — a machine-checked "
            "contract + a tier of CI gates that must be green before merge. Name the concrete pieces: "
            "contract lint, the tier/gate ladder, the provider-agnostic review panel, auto blast-radius "
            "classification, `orient` (a symbol map), the PR-native comment, and the MCP server that lets "
            "an agent call the whole loop. Emphasize enforcement-at-authoring, not review-time."
        ),
    },
    "eng-leaders": {
        "who": "an engineering leader / EM deciding whether to adopt a governance framework across teams",
        "angle": (
            "Frame around consistency and accountability at team scale: today quality depends on which "
            "operator did the work. Trellis turns your standards into gates every change must pass, and "
            "reports honest metrics (gate pass-rate, rubber-stamp rate, defect-escape from reverts). "
            "Stress low adoption cost — it's a CLI + a CI workflow + an MCP server, tool-agnostic and "
            "dependency-light, not a hosted platform to buy."
        ),
    },
    "investors": {
        "who": "a technical investor assessing the wedge and the market",
        "angle": (
            "Position the shift: the industry is moving to agentic coding, and the open question is who "
            "owns the governance layer agents call. Trellis is that layer — contract-first gates plus an "
            "MCP server so any agent (Claude Code, Cursor) runs the same governed loop. Keep it crisp on "
            "the wedge (enforcement, not advice), the moat (dogfooded, open-source, standards-shaped), and "
            "the roadmap to distribution (PyPI, policy packs)."
        ),
    },
    "oss": {
        "who": "an open-source developer who might adopt or contribute to Trellis",
        "angle": (
            "Welcoming and concrete: what it does, how to install (`pip install trellis-loop`), the "
            "one-command onboarding (`trellis init`, `trellis draft` from a PRD), and how it governs its "
            "own repo (dogfooding). Invite contribution: Apache-2.0, small stdlib core, clear extension "
            "points (shell-command review lenses, tree-sitter extractors, policy packs)."
        ),
    },
}

TONES = {
    "energetic": "Energetic and confident, but technically honest — no hype words, no vague superlatives.",
    "calm": "Calm, measured, documentary — let the substance carry it.",
    "punchy": "Punchy and fast — short sentences, strong verbs, one idea per beat.",
}


def collect_sources(repo: Path = REPO):
    """Return [(path, why, text)] for the sources that exist."""
    out = []
    for rel, why in SOURCES:
        p = repo / rel
        if p.is_file():
            out.append((rel, why, p.read_text(encoding="utf-8")))
    return out


def build_source_pack(repo: Path = REPO, extra=None) -> str:
    parts = [
        "# Trellis — project source pack (for a NotebookLM overview)",
        "",
        "> This single document bundles the Trellis project's own materials so a NotebookLM "
        "notebook has one clean, coherent source to narrate. Each section below is a real file "
        "from the repository.",
        "",
    ]
    for rel, why, text in collect_sources(repo):
        parts += [f"\n\n{'=' * 78}", f"## SOURCE: {rel}", f"_Why this matters: {why}_", f"{'=' * 78}\n", text]
    for title, why, text in (extra or []):
        parts += [f"\n\n{'=' * 78}", f"## SOURCE: {title}", f"_Why this matters: {why}_", f"{'=' * 78}\n", text]
    return "\n".join(parts)


SAMPLE_PRD = """# Login throttle

Rate-limit failed logins so credential-stuffing can't brute-force accounts.

## Acceptance
- must reject after 5 failed attempts within 60 seconds for the same account
- must return HTTP 429 with a Retry-After header
- must not lock out a user whose attempts are all successful

## Out of scope
- CAPTCHA, IP reputation
"""


def _display(cmd, repo: Path):
    """Shorten absolute repo paths so the transcript reads cleanly."""
    return [c.replace(str(repo) + "/", "./").replace(str(repo), ".") for c in cmd]


def _run(cmd, cwd, stdin=None, limit=22):
    import subprocess
    try:
        p = subprocess.run(cmd, cwd=str(cwd), input=stdin, capture_output=True, text=True, timeout=180)
        out = ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as exc:  # noqa: BLE001
        out = f"[could not run: {exc}]"
    lines = out.splitlines() or ["(no output)"]
    if len(lines) > limit:
        lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
    return "\n".join(lines)


def capture_cli_demo(repo: Path = REPO, trellis: str = "trellis") -> str:
    """Run a real Trellis walkthrough and return it as a Markdown transcript.

    A visual, in-action source for the video — every command and its output is real.
    """
    import shutil
    import subprocess
    import tempfile

    blocks = [
        "# Trellis — captured CLI session",
        "",
        "> Real commands and real output, so the overview can show the tool actually running "
        "(these double as the 'screenshots' of the walkthrough).",
    ]
    tmp = Path(tempfile.mkdtemp(prefix="trellis-demo-"))
    try:
        subprocess.run(["git", "init", "-q", "."], cwd=str(tmp))
        (tmp / "login-throttle.prd.md").write_text(SAMPLE_PRD, encoding="utf-8")
        steps = [
            ("Scaffold governance into a repo", [trellis, "init", "--preset", "python"], tmp, None),
            ("Draft a contract from a PRD",
             [trellis, "draft", "login-throttle.prd.md", "--id", "login-throttle"], tmp, None),
            ("Validate the contract (machine-checked)",
             [trellis, "lint", "contracts/login-throttle.md"], tmp, None),
            ("Map the code — orient",
             [trellis, "orient", "--path", str(repo / "src" / "trellis"), "--budget", "350"], repo, None),
            ("Agent-native — list the MCP tools", [trellis, "mcp"], repo,
             '{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n'),
        ]
        # NOTE: no live `trellis gate` step — the scoped gate runs the test suite, and this capture
        # is itself exercised by a test, so running it here would recurse. Gates are narrated in the
        # prompt + beat sheet instead. The GIF tape (demo.tape) shows a live gate in a scratch dir.
        for title, cmd, cwd, stdin in steps:
            shown = " ".join(_display(cmd, repo))
            if stdin:
                shown = "echo '<jsonrpc>' | " + shown
            blocks.append(f"\n## {title}\n\n```console\n$ {shown}\n{_run(cmd, cwd, stdin)}\n```")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "\n".join(blocks)


def build_prompt(audience: str, fmt: str, minutes: int, tone: str) -> str:
    a = AUDIENCES[audience]
    medium = "video overview" if fmt == "video" else "audio overview (podcast-style)"
    return "\n".join([
        f"Create a ~{minutes}-minute {medium} about Trellis for {a['who']}.",
        "",
        "What Trellis is (one line): a contract-first, gate-enforced software-development governance "
        "framework — it turns best-practices into CI gates a change cannot merge without passing.",
        "",
        f"Angle & content: {a['angle']}",
        "",
        f"Tone: {TONES[tone]}",
        "",
        "Structure:",
        "  1. Hook — the problem (rigor that's generated but not guaranteed).",
        "  2. The idea — machine-checked contract + tier of gates; skipping = a failing build.",
        "  3. The pieces — walk the loop concretely (draft -> contract -> gate -> review -> PR comment).",
        "  4. Why it's different — enforcement at authoring; tool-agnostic; agent-native via MCP.",
        "  5. Close — how to try it (`pip install trellis-loop`, `trellis init`), open-source (Apache-2.0).",
        "",
        "Do NOT: invent features not in the sources, overstate maturity (it's an early beta), or use "
        "marketing filler. Ground every claim in the provided sources.",
    ])


def build_steps(audience: str, fmt: str, minutes: int, out_dir: Path) -> str:
    medium = "Video Overview" if fmt == "video" else "Audio Overview"
    return "\n".join([
        f"# Producing the Trellis video with NotebookLM ({audience}, {fmt}, ~{minutes} min)",
        "",
        "NotebookLM has no API, so these steps are manual (2-3 minutes of clicking):",
        "",
        "1. Go to https://notebooklm.google.com and click **Create new notebook**.",
        f"2. **Add source** -> upload `{out_dir / 'source-pack.md'}`",
        "   (or paste its contents as a text source). This is the only source you need.",
        f"3. In the Studio panel, choose **{medium}**.",
        "4. Click **Customize**, then paste the contents of "
        f"`{out_dir / 'prompt.txt'}` into the instruction box.",
        "5. Click **Generate**. It takes a few minutes.",
        f"6. When ready, **download** the {fmt} and share it.",
        "",
        "Tip: re-run this script with different flags to retarget —",
        "  `--audience investors --format audio --minutes 6 --tone punchy`",
        "",
        "---",
        "",
        "## Narration beat sheet (fallback human script)",
        "",
        "If you'd rather record it yourself (or hand a human narrator a script), here are the beats.",
        f"Aim for ~{minutes} minutes; ~{max(1, minutes * 130)} words total (~130 wpm).",
        "",
        "- **[0:00] Hook.** Most AI (and human) dev workflows *generate* rigor — a spec, a review, a "
        "Definition of Done — but don't *guarantee* it. The standard lives in a doc; following it is a "
        "judgment call.",
        "- **[0:20] The turn.** Trellis makes rigor mechanical: a change declares a machine-checked "
        "*contract*, and a *tier of gates* must be green before it can merge. Skipping the process "
        "becomes a failing build.",
        "- **[0:50] The loop.** Draft a contract from a PRD -> lint it -> classify the change's "
        "blast-radius into a tier -> run the tier's gates (tests, ADR, review) -> a provider-agnostic "
        "review panel of shell-command lenses -> a PR comment with the gate table + findings.",
        "- **[2:00] Why it's different.** Enforcement happens at *authoring*, not review. It's "
        "tool-agnostic and dependency-light — and agent-native: an MCP server lets Claude Code or "
        "Cursor call the same governed loop mid-task.",
        "- **[3:00] Close.** Open-source, Apache-2.0. `pip install trellis-loop`, then `trellis init`. "
        "It even governs its own repo.",
    ])


def prepare(audience: str, fmt: str, minutes: int, tone: str, out_dir: Path,
            repo: Path = REPO, with_demo: bool = False):
    out_dir.mkdir(parents=True, exist_ok=True)
    extra = []
    if with_demo:
        demo = capture_cli_demo(repo)
        (out_dir / "cli-demo.md").write_text(demo + "\n", encoding="utf-8")
        extra.append(("CLI demo (captured session)",
                      "Shows the tool actually running — concrete commands + output for the video.", demo))
    pack = build_source_pack(repo, extra=extra)
    prompt = build_prompt(audience, fmt, minutes, tone)
    steps = build_steps(audience, fmt, minutes, out_dir)
    (out_dir / "source-pack.md").write_text(pack, encoding="utf-8")
    (out_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    (out_dir / "STEPS.md").write_text(steps + "\n", encoding="utf-8")
    return pack, prompt, steps


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Prepare a NotebookLM video source pack + prompt for Trellis.")
    ap.add_argument("--audience", choices=sorted(AUDIENCES), default="developers")
    ap.add_argument("--format", dest="fmt", choices=["video", "audio"], default="video")
    ap.add_argument("--minutes", type=int, default=4)
    ap.add_argument("--tone", choices=sorted(TONES), default="energetic")
    ap.add_argument("--with-demo", action="store_true",
                    help="run a live Trellis walkthrough and add the captured session as a source")
    ap.add_argument("--out-dir", default=str(REPO / "build" / "notebooklm"))
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    pack, prompt, _ = prepare(args.audience, args.fmt, args.minutes, args.tone, out_dir, REPO,
                              with_demo=args.with_demo)
    n_sources = len(collect_sources(REPO)) + (1 if args.with_demo else 0)
    print(f"Prepared NotebookLM inputs in {out_dir}/")
    print(f"  source-pack.md  ({n_sources} sources, {len(pack.splitlines())} lines)"
          + ("  [+ captured CLI demo]" if args.with_demo else ""))
    print("  prompt.txt      (paste into NotebookLM 'Customize')")
    print("  STEPS.md        (upload + generate steps + narration beat sheet)")
    print("\n--- steering prompt preview ---\n")
    print(prompt)
    print(f"\nNext: open https://notebooklm.google.com, upload source-pack.md, "
          f"choose {args.fmt.title()} Overview, Customize -> paste prompt.txt -> Generate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
