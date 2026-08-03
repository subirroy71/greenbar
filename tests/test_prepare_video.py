"""The NotebookLM video-prep script assembles a source pack + steering prompt."""
import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "notebooklm" / "prepare_video.py"
_spec = importlib.util.spec_from_file_location("prepare_video", _SCRIPT)
pv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pv)


def test_source_pack_bundles_real_repo_files():
    pack = pv.build_source_pack()
    assert "SOURCE: README.md" in pack and "SOURCE: CHANGELOG.md" in pack
    assert "contract-first" in pack.lower()


def test_prompt_is_audience_tuned():
    dev = pv.build_prompt("developers", "video", 4, "energetic")
    inv = pv.build_prompt("investors", "audio", 6, "punchy")
    assert "4-minute video overview" in dev and "senior software engineer" in dev
    assert "6-minute audio overview" in inv and "investor" in inv
    assert dev != inv  # the angle actually changes with audience


def test_prepare_writes_three_artifacts(tmp_path):
    out = tmp_path / "nb"
    pv.prepare("oss", "audio", 5, "calm", out)
    assert (out / "source-pack.md").exists()
    assert "pip install trellis-loop" in (out / "prompt.txt").read_text()
    steps = (out / "STEPS.md").read_text()
    assert "notebooklm.google.com" in steps and "beat sheet" in steps.lower()


def test_capture_cli_demo_runs_real_commands():
    demo = pv.capture_cli_demo()
    # every step header present, and real output for at least the read-only ones
    assert "orient" in demo and "MCP tools" in demo
    assert "```console" in demo and "trellis_orient" in demo  # a real MCP tools/list response


def test_with_demo_adds_a_source(tmp_path):
    out = tmp_path / "nb"
    pack, _, _ = pv.prepare("developers", "video", 4, "energetic", out, with_demo=True)
    assert (out / "cli-demo.md").exists()
    assert "captured session" in pack.lower()


def test_cli_runs(capsys):
    assert pv.main(["--audience", "eng-leaders", "--minutes", "3", "--out-dir",
                    str(Path(pv.REPO) / "build" / "notebooklm-test")]) == 0
    assert "steering prompt preview" in capsys.readouterr().out
