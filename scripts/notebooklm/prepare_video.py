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


def build_source_pack(repo: Path = REPO) -> str:
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
    return "\n".join(parts)


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


def prepare(audience: str, fmt: str, minutes: int, tone: str, out_dir: Path, repo: Path = REPO):
    out_dir.mkdir(parents=True, exist_ok=True)
    pack = build_source_pack(repo)
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
    ap.add_argument("--out-dir", default=str(REPO / "build" / "notebooklm"))
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    pack, prompt, _ = prepare(args.audience, args.fmt, args.minutes, args.tone, out_dir, REPO)
    n_sources = len(collect_sources(REPO))
    print(f"Prepared NotebookLM inputs in {out_dir}/")
    print(f"  source-pack.md  ({n_sources} sources, {len(pack.splitlines())} lines)")
    print("  prompt.txt      (paste into NotebookLM 'Customize')")
    print("  STEPS.md        (upload + generate steps + narration beat sheet)")
    print("\n--- steering prompt preview ---\n")
    print(prompt)
    print(f"\nNext: open https://notebooklm.google.com, upload source-pack.md, "
          f"choose {args.fmt.title()} Overview, Customize -> paste prompt.txt -> Generate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
