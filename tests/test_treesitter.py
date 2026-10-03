"""Polyglot orient — extractor dispatch + graceful fallback (always run) and the real tree-sitter
extractor (skipped cleanly when the optional extra is absent)."""
import pytest

from greenbar import treesitter as ts
from greenbar.orient import PythonAstExtractor, Symbol, build_graph, default_extractors


# ---- always run: these don't need the optional extra ----

def test_default_extractors_always_has_python():
    assert any(isinstance(e, PythonAstExtractor) for e in default_extractors())


def test_available_returns_bool():
    assert isinstance(ts.available(), bool)


def test_extractors_empty_when_extra_absent(monkeypatch):
    monkeypatch.setattr(ts, "available", lambda: False)
    assert ts.treesitter_extractors() == []


def test_build_graph_dispatches_by_extension(tmp_path):
    class FakeJs:
        extensions = (".fake",)

        def extract(self, path, source):
            return [Symbol(f"{path}::X", "X", "def", path, 1, "def X()")], []

    (tmp_path / "a.py").write_text("def pyfn():\n    return 1\n")
    (tmp_path / "b.fake").write_text("anything")
    g = build_graph(tmp_path, extractors=[PythonAstExtractor(), FakeJs()])
    assert "pyfn" in g.by_name  # .py → stdlib ast
    assert "X" in g.by_name     # .fake → the fake extractor (A3)


def test_unsupported_file_is_skipped(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return 1\n")
    (tmp_path / "image.bin").write_text("not code")
    g = build_graph(tmp_path, extractors=[PythonAstExtractor()])
    assert "f" in g.by_name  # .bin ignored, no crash (A4)


# ---- real tree-sitter (skips when `pip install greenbar[treesitter]` isn't present) ----

def test_treesitter_extracts_js_and_go(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "m.js").write_text("function hi(){ return there(); }\nfunction there(){ return 1; }\n")
    (tmp_path / "m.go").write_text(
        "package main\nfunc Hi() int { return There() }\nfunc There() int { return 1 }\n"
    )
    g = build_graph(tmp_path)  # default extractors include tree-sitter when installed
    assert "hi" in g.by_name and "there" in g.by_name  # JavaScript (A1)
    assert "Hi" in g.by_name and "There" in g.by_name  # Go (A1)


def test_treesitter_c_family_and_edges(tmp_path):
    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "m.cpp").write_text(
        "int helper(){ return 1; }\nint add(){ return helper(); }\nclass Widget { void render(){} };\n"
    )
    g = build_graph(tmp_path)
    assert "add" in g.by_name and "helper" in g.by_name
    assert "Widget" in g.by_name or "render" in g.by_name
    # name-based edge resolves across the C++ file too
    add_id = g.by_name["add"][0]
    helper_id = g.by_name["helper"][0]
    assert helper_id in g.out_edges.get(add_id, [])
