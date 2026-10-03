"""`greenbar orient` — a token-bounded, rank-ordered code map for agent orientation.

The one big rtscale-loop capability Greenbar lacked: instead of reading 15k tokens of files to find
where to look, build a symbol graph of the repo and emit a compact map of the most relevant
symbols — and, focused on a diff, "what does this change touch and connect to."

Dependency-light: Python is parsed with the stdlib ``ast`` module (no deps). The extractor is a
small interface (:class:`Extractor`) so tree-sitter / other languages plug in as an optional extra
without touching core. The graph is approximate (name-based edges, like a repo map) — an advisory
read-replica of the code, to be verified against the source, exactly as graphify is used.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Set, Tuple


@dataclass(frozen=True)
class Symbol:
    node_id: str        # unique: "path::qualname"
    name: str           # simple name (used for name-based edge resolution)
    kind: str           # "def" | "class" | "method"
    file: str
    line: int
    signature: str


class Extractor(Protocol):
    """Return (symbols, references) for a file. A reference is (defining node_id, referenced name);
    references are resolved to targets globally by :func:`build_graph`."""

    extensions: Tuple[str, ...]

    def extract(self, path: str, source: str) -> Tuple[List[Symbol], List[Tuple[str, str]]]:
        ...


def _signature(node: ast.AST) -> str:
    try:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return f"def {node.name}({ast.unparse(node.args)})"
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            return f"class {node.name}" + (f"({bases})" if bases else "")
    except Exception:  # noqa: BLE001 — unparse can fail on odd trees; degrade to the name
        pass
    return getattr(node, "name", "?")


class PythonAstExtractor:
    extensions = (".py",)

    def extract(self, path: str, source: str) -> Tuple[List[Symbol], List[Tuple[str, str]]]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return [], []  # A3: a broken file is skipped, not fatal
        symbols: List[Symbol] = []
        refs: List[Tuple[str, str]] = []

        def _qual(stack: List[str], name: str) -> str:
            return ".".join([*stack, name])

        def walk(node: ast.AST, stack: List[str], enclosing: Optional[str]) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qual = _qual(stack, child.name)
                    node_id = f"{path}::{qual}"
                    kind = "class" if isinstance(child, ast.ClassDef) else ("method" if stack else "def")
                    symbols.append(Symbol(node_id, child.name, kind, path, child.lineno, _signature(child)))
                    # references made in THIS symbol's body point outward from it
                    for ref_name in _referenced_names(child):
                        refs.append((node_id, ref_name))
                    walk(child, [*stack, child.name], node_id)

        walk(tree, [], None)
        return symbols, refs


def _referenced_names(node: ast.AST) -> Set[str]:
    """Names this def references — called functions and attribute/name loads — for edge building.
    Excludes nested-def names (those are separate nodes)."""
    names: Set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            f = child.func
            if isinstance(f, ast.Name):
                names.add(f.id)
            elif isinstance(f, ast.Attribute):
                names.add(f.attr)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


@dataclass
class Graph:
    symbols: Dict[str, Symbol] = field(default_factory=dict)         # node_id -> Symbol
    out_edges: Dict[str, List[str]] = field(default_factory=dict)    # node_id -> [node_id]
    by_name: Dict[str, List[str]] = field(default_factory=dict)      # name -> [node_id]


def _iter_source_files(root: Path, extensions: Tuple[str, ...], exclude: Iterable[str]) -> List[Path]:
    ex = tuple(exclude)
    out: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in extensions:
            continue
        rel = p.relative_to(root).as_posix()
        if any(seg in rel.split("/") for seg in ex) or rel.startswith(tuple(ex)):
            continue
        out.append(p)
    return out


def default_extractors() -> List[Extractor]:
    """Python (stdlib, always) + tree-sitter languages IF the optional extra is installed."""
    exts: List[Extractor] = [PythonAstExtractor()]
    try:
        from .treesitter import treesitter_extractors
        exts.extend(treesitter_extractors())
    except Exception:  # noqa: BLE001 — extra absent / import issue → Python-only (A2)
        pass
    return exts


def build_graph(root: str | Path, extractors: Optional[List[Extractor]] = None,
                exclude: Iterable[str] = (".git", "__pycache__", ".venv", "venv", "build", "dist")) -> Graph:
    extractors = extractors or default_extractors()
    # dispatch table: extension -> extractor (first registered wins; Python is first)
    by_ext: Dict[str, Extractor] = {}
    for ex in extractors:
        for e in ex.extensions:
            by_ext.setdefault(e, ex)
    root = Path(root)
    g = Graph()
    raw_refs: List[Tuple[str, str]] = []
    for path in _iter_source_files(root, tuple(by_ext), exclude):
        rel = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            continue
        symbols, refs = by_ext[path.suffix].extract(rel, source)  # A3: dispatch by extension
        for s in symbols:
            g.symbols[s.node_id] = s
            g.by_name.setdefault(s.name, []).append(s.node_id)
        raw_refs.extend(refs)
    # resolve name references to target node_ids (approximate: by simple name)
    for src_id, ref_name in raw_refs:
        for tgt_id in g.by_name.get(ref_name, ()):
            if tgt_id != src_id:
                g.out_edges.setdefault(src_id, []).append(tgt_id)
    return g


def pagerank(g: Graph, personalization: Optional[Dict[str, float]] = None,
             damping: float = 0.85, iters: int = 30) -> Dict[str, float]:
    nodes = list(g.symbols)
    n = len(nodes)
    if n == 0:
        return {}
    if personalization:
        s = sum(personalization.values()) or 1.0
        p = {node: personalization.get(node, 0.0) / s for node in nodes}
    else:
        p = {node: 1.0 / n for node in nodes}
    rank = {node: 1.0 / n for node in nodes}
    for _ in range(iters):
        new = {node: (1 - damping) * p[node] for node in nodes}
        for node in nodes:
            outs = g.out_edges.get(node) or []
            if outs:
                share = damping * rank[node] / len(outs)
                for m in outs:
                    new[m] = new.get(m, 0.0) + share
            else:  # dangling mass → personalization
                for m in nodes:
                    new[m] += damping * rank[node] * p[m]
        rank = new
    return rank


def rank_symbols(g: Graph, focus_files: Optional[Set[str]] = None) -> List[Tuple[Symbol, float]]:
    personalization = None
    if focus_files:
        personalization = {nid: 1.0 for nid, s in g.symbols.items() if s.file in focus_files}
        if not personalization:  # focus files carry no symbols → fall back to uniform
            personalization = None
    scores = pagerank(g, personalization)
    ranked = sorted(g.symbols.values(), key=lambda s: (-scores.get(s.node_id, 0.0), s.file, s.line))
    return [(s, scores.get(s.node_id, 0.0)) for s in ranked]


def render_map(ranked: List[Tuple[Symbol, float]], budget_tokens: int = 1200) -> str:
    """Emit the top symbols grouped by file, until ~budget_tokens (est. 4 chars/token) is hit."""
    budget_chars = budget_tokens * 4
    lines: List[str] = []
    used = 0
    current_file = None
    for sym, _score in ranked:
        entry = f"  {sym.file}:{sym.line}  {sym.signature}"
        header = "" if sym.file == current_file else f"\n{sym.file}\n"
        cost = len(entry) + len(header)
        if used + cost > budget_chars and lines:
            break
        if header:
            lines.append(header.rstrip("\n"))
            current_file = sym.file
        lines.append(entry)
        used += cost
    return "\n".join(lines).strip()
