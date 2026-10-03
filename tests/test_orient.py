"""`greenbar orient` — the symbol graph, diff-focused ranking, budget, and fail-safety."""
from greenbar.orient import (
    PythonAstExtractor,
    build_graph,
    pagerank,
    rank_symbols,
    render_map,
)


def _write(tmp_path, rel, text):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_extractor_finds_defs_classes_methods():
    src = (
        "def top(a, b):\n"
        "    return helper(a)\n"
        "\n"
        "class Widget:\n"
        "    def render(self):\n"
        "        return top(1, 2)\n"
        "\n"
        "def helper(x):\n"
        "    return x\n"
    )
    syms, refs = PythonAstExtractor().extract("m.py", src)
    kinds = {(s.name, s.kind) for s in syms}
    assert ("top", "def") in kinds
    assert ("Widget", "class") in kinds
    assert ("render", "method") in kinds
    # 'top' references 'helper'; 'render' references 'top' → those names appear in refs
    ref_names = {r[1] for r in refs}
    assert "helper" in ref_names and "top" in ref_names


def test_broken_file_is_skipped_not_fatal(tmp_path):
    _write(tmp_path, "ok.py", "def a():\n    return b()\ndef b():\n    return 1\n")
    _write(tmp_path, "broken.py", "def a(:\n  oops\n")  # SyntaxError
    g = build_graph(tmp_path)
    assert "a" in g.by_name and "b" in g.by_name  # ok.py parsed
    # graph built despite broken.py (A3)


def test_graph_edges_resolve_by_name(tmp_path):
    _write(tmp_path, "m.py", "def caller():\n    return callee()\ndef callee():\n    return 1\n")
    g = build_graph(tmp_path)
    caller = g.by_name["caller"][0]
    callee = g.by_name["callee"][0]
    assert callee in g.out_edges.get(caller, [])


def test_ranking_biases_toward_focus_files(tmp_path):
    # two islands of equal shape; focusing on one file must rank its symbols above the other's
    _write(tmp_path, "a.py", "def a1():\n    return a2()\ndef a2():\n    return 1\n")
    _write(tmp_path, "b.py", "def b1():\n    return b2()\ndef b2():\n    return 1\n")
    g = build_graph(tmp_path)
    ranked = rank_symbols(g, focus_files={"a.py"})
    top_files = [s.file for s, _ in ranked[:2]]
    assert top_files == ["a.py", "a.py"]  # focused island floats to the top


def test_render_respects_budget(tmp_path):
    for i in range(50):
        _write(tmp_path, f"f{i}.py", f"def fn{i}():\n    return {i}\n")
    g = build_graph(tmp_path)
    ranked = rank_symbols(g)
    tiny = render_map(ranked, budget_tokens=20)   # ~80 chars
    big = render_map(ranked, budget_tokens=2000)
    assert len(tiny) < len(big)
    assert len(tiny) <= 20 * 4 + 200  # within budget (+ one-entry overshoot allowance)


def test_empty_repo_yields_empty_map(tmp_path):
    g = build_graph(tmp_path)
    assert g.symbols == {}
    assert pagerank(g) == {}
    assert render_map(rank_symbols(g)) == ""  # no crash on empty
