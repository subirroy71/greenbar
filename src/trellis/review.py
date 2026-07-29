"""`trellis review` — convene independent lenses on a change and emit a review record.

Provider-agnostic by design: a *lens* is a shell command. It receives the prompt (persona +
contract + diff) on stdin and prints its review ending in a JSON verdict object; a
``deterministic: true`` lens (a static analyzer, type checker, …) derives its verdict from the exit
code instead. Trellis calls no LLM directly — it orchestrates whatever command you wire, so
cross-model review is just "different command per lens", and the tool stays dependency-light.

Fail-closed: a lens that times out, crashes, or emits no parseable verdict is recorded as ERROR —
never a silent SIGN. The record carries a context hash so you can prove which tree was reviewed.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

VERDICTS = {"SIGN", "SIGN_WITH_CHANGE", "BLOCK", "ERROR"}
_BLOCKING = {"BLOCK", "ERROR"}

_RETURN_CONTRACT = (
    "\nTrace the change against the REAL code, not this description. Be rigorous and independent —"
    " don't rubber-stamp, but don't invent problems; if it's sound, SIGN and say why. End your"
    " reply with a single JSON object on its own line:\n"
    '  {"verdict": "SIGN" | "SIGN_WITH_CHANGE" | "BLOCK", "findings": ["<issue + file:line + why>"]}\n'
)


def normalize_verdict(s: Optional[str]) -> str:
    if not s:
        return "ERROR"
    t = str(s).strip().upper().replace("-", "_").replace(" ", "_")
    if t in ("SIGN", "APPROVE", "LGTM", "PASS"):
        return "SIGN"
    if t in ("SIGN_WITH_CHANGE", "SIGN_WITH_CHANGES", "CHANGES", "REQUEST_CHANGES"):
        return "SIGN_WITH_CHANGE"
    if t in ("BLOCK", "REJECT", "FAIL"):
        return "BLOCK"
    return t if t in VERDICTS else "ERROR"


def parse_verdict_json(text: str) -> Optional[dict]:
    """Return the LAST JSON object in ``text`` that carries a "verdict" key (robust to prose and to
    braces inside finding strings — uses the JSON decoder, not a regex)."""
    dec = json.JSONDecoder()
    best = None
    i = 0
    while True:
        idx = text.find("{", i)
        if idx == -1:
            break
        try:
            obj, end = dec.raw_decode(text, idx)
            if isinstance(obj, dict) and "verdict" in obj:
                best = obj
            i = max(end, idx + 1)
        except json.JSONDecodeError:
            i = idx + 1
    return best


@dataclass
class LensResult:
    name: str
    verdict: str
    findings: List[str] = field(default_factory=list)
    provider: str = "command"
    error: Optional[str] = None
    raw_excerpt: str = ""


def build_prompt(lens: dict, contract_text: str, diff: str) -> str:
    persona = lens.get("persona") or "You are a rigorous, independent code reviewer."
    return (
        f"{persona}\n\n## Contract\n{contract_text or '(none)'}\n\n"
        f"## Diff under review\n{diff or '(no diff provided)'}\n{_RETURN_CONTRACT}"
    )


def run_command_lens(lens: dict, contract_text: str, diff: str, timeout_s: float) -> LensResult:
    name = lens.get("name", "?")
    cmd = lens.get("command")
    if not cmd:
        return LensResult(name, "ERROR", error="lens has no 'command'")
    prompt = build_prompt(lens, contract_text, diff)
    try:
        proc = subprocess.run(
            cmd, shell=True, input=prompt, capture_output=True, text=True, timeout=timeout_s
        )
    except subprocess.TimeoutExpired:
        return LensResult(name, "ERROR", error=f"timed out after {timeout_s}s")
    except Exception as exc:  # noqa: BLE001 — a broken command must not crash the run
        return LensResult(name, "ERROR", error=f"lens failed to run: {exc}")

    out = proc.stdout or ""
    combined = (out + ("\n" + proc.stderr if proc.stderr else "")).strip()
    if lens.get("deterministic"):
        ok = proc.returncode == 0
        return LensResult(
            name,
            "SIGN" if ok else "BLOCK",
            findings=[] if ok else [combined[:800] or f"exit {proc.returncode}"],
            provider="deterministic",
            raw_excerpt=combined[-1000:],
        )
    parsed = parse_verdict_json(out)
    if parsed is None:
        return LensResult(name, "ERROR", error="no parseable verdict JSON in output", raw_excerpt=out[-1000:])
    findings = [str(x) for x in (parsed.get("findings") or [])]
    return LensResult(name, normalize_verdict(parsed.get("verdict")), findings, raw_excerpt=out[-1000:])


def _summarize(results: List[LensResult]) -> tuple[dict, dict]:
    signs = [r for r in results if r.verdict == "SIGN"]
    changes = [r for r in results if r.verdict == "SIGN_WITH_CHANGE"]
    blockers = [r for r in results if r.verdict in _BLOCKING]
    total_findings = sum(len(r.findings) for r in results)
    all_sign_no_findings = bool(results) and len(signs) == len(results) and total_findings == 0
    verdict = "BLOCKED" if blockers else ("CHANGES" if changes else "PASS")
    summary = {
        "verdict": verdict,
        "signs": len(signs),
        "changes": len(changes),
        "blockers": len(blockers),
    }
    metrics = {
        "lens_count": len(results),
        "sign_rate": (len(signs) / len(results)) if results else 0.0,
        "finding_count": total_findings,
        "all_sign_no_findings": all_sign_no_findings,  # a rubber-stamp smell
    }
    return summary, metrics


def run_review(
    contract_path: Optional[str],
    config: dict,
    diff: str,
    *,
    now: str,
    out_path: str = ".trellis/review-record.json",
    run_lens: Optional[Callable[[dict, str, str, float], LensResult]] = None,
) -> dict:
    """Run every configured lens (in parallel), synthesize, and persist the record.

    ``run_lens`` is injectable for testing; production uses :func:`run_command_lens`.
    """
    lenses = config.get("lenses") or []
    review = config.get("review") or {}
    timeout_s = float(review.get("timeout_s", 300))
    parallelism = int(review.get("parallelism", 4))
    runner = run_lens or run_command_lens

    contract_text = Path(contract_path).read_text() if contract_path and Path(contract_path).exists() else ""
    context = contract_text + "\n---DIFF---\n" + (diff or "")
    context_hash = hashlib.sha256(context.encode()).hexdigest()[:16]
    contract_hash = hashlib.sha256(contract_text.encode()).hexdigest()[:16] if contract_text else None

    if lenses:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, parallelism)) as ex:
            results = list(ex.map(lambda l: runner(l, contract_text, diff, timeout_s), lenses))
    else:
        results = []

    summary, metrics = _summarize(results)
    record = {
        "contract": str(contract_path) if contract_path else None,
        "contract_hash": contract_hash,
        "context_hash": context_hash,
        "created_at": now,
        "lenses": [asdict(r) for r in results],
        "summary": summary,
        "metrics": metrics,
    }
    outp = Path(out_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(record, indent=2))
    return record


def check_review_record(
    contract: Optional[str],
    record_path: str = ".trellis/review-record.json",
    *,
    fail_on_rubber_stamp: bool = False,
) -> tuple[bool, str]:
    """Gate helper: a fresh, non-BLOCK review record for the current contract must exist."""
    p = Path(record_path)
    if not p.exists():
        return (False, f"no review record at {record_path} — run `trellis review`")
    try:
        rec = json.loads(p.read_text())
    except Exception as exc:  # noqa: BLE001
        return (False, f"review record is not valid JSON: {exc}")
    if contract and Path(contract).exists():
        cur = hashlib.sha256(Path(contract).read_text().encode()).hexdigest()[:16]
        if rec.get("contract_hash") != cur:
            return (False, "review record is STALE — it doesn't match the current contract; re-run `trellis review`")
    sv = (rec.get("summary") or {}).get("verdict")
    if sv == "BLOCKED":
        return (False, f"review is BLOCKED ({(rec.get('summary') or {}).get('blockers')} blocking lens)")
    if fail_on_rubber_stamp and (rec.get("metrics") or {}).get("all_sign_no_findings"):
        return (False, "every lens SIGNed with zero findings — looks like a rubber stamp")
    return (True, f"review {sv} · {(rec.get('metrics') or {}).get('lens_count')} lenses")
