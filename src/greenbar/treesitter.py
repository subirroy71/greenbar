"""Optional multi-language extractor for `greenbar orient` — `pip install greenbar[treesitter]`.

Implements the same `Extractor` interface as the stdlib-`ast` Python extractor, using
``tree-sitter-language-pack`` (prebuilt grammars) + a compact node-type table. This gives orient
graphify-like polyglot reach (JS/TS, Go, Rust, Java, C/C++, Kotlin, Swift, Ruby, C#, …) WITHOUT
adding anything to Greenbar's core dependencies — it is imported lazily and, if the extra isn't
installed, orient runs Python-only with no error.

The cross-language graph is orientation-grade (name-based edges), an advisory read-replica to be
verified against source — same discipline as the rest of orient.
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Set, Tuple

from .orient import Symbol

# extension → tree-sitter-language-pack language name
_LANG_BY_EXT = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
    ".go": "go", ".rs": "rust", ".java": "java", ".rb": "ruby",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift", ".cs": "csharp", ".php": "php",
    ".scala": "scala", ".rb2": "ruby",
}

# definition node types (across grammars) → symbol kind
_DEF_KIND = {
    "function_declaration": "def", "function_definition": "def", "function_item": "def",
    "function_signature": "def", "func_literal": "def", "arrow_function": "def",
    "method_definition": "method", "method_declaration": "method", "constructor_declaration": "method",
    "class_declaration": "class", "class_definition": "class", "class_specifier": "class",
    "struct_specifier": "class", "struct_item": "class", "interface_declaration": "class",
    "impl_item": "class", "trait_item": "class", "object_declaration": "class",
    "enum_declaration": "class", "enum_specifier": "class", "type_alias_declaration": "def",
    "protocol_declaration": "class",
}


def available() -> bool:
    try:
        import tree_sitter_language_pack  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


class TreeSitterExtractor:
    def __init__(self, language: str, extensions: Tuple[str, ...]):
        self.language = language
        self.extensions = extensions
        self._parser = None  # None=untried, False=unavailable, else a parser

    def _get_parser(self):
        if self._parser is None:
            try:
                from tree_sitter_language_pack import get_parser
                self._parser = get_parser(self.language)
            except Exception:  # noqa: BLE001 — grammar missing for this language → skip it
                self._parser = False
        return self._parser or None

    def extract(self, path: str, source: str) -> Tuple[List[Symbol], List[Tuple[str, str]]]:
        parser = self._get_parser()
        if parser is None:
            return [], []
        try:
            tree = parser.parse(bytes(source, "utf-8"))
        except Exception:  # noqa: BLE001 — parse failure is skipped, not fatal (A4)
            return [], []

        symbols: List[Symbol] = []
        refs: List[Tuple[str, str]] = []

        def _text(node) -> str:
            try:
                return node.text.decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                return ""

        def _first_identifier(node):
            # BFS for a name identifier; prefer a plain identifier over a type_identifier
            from collections import deque
            q = deque(node.children)
            fallback = None
            while q:
                c = q.popleft()
                t = c.type
                if t in ("identifier", "field_identifier", "property_identifier", "simple_identifier"):
                    return _text(c)
                if t.endswith("identifier") and t != "type_identifier" and fallback is None:
                    fallback = _text(c)
                q.extend(c.children)
            return fallback

        def _name(node):
            f = node.child_by_field_name("name")
            if f is not None:
                return _text(f)
            # C / C++ put the name inside a `declarator`; recurse into it first
            d = node.child_by_field_name("declarator")
            if d is not None:
                ident = _first_identifier(d)
                if ident:
                    return ident
            return _first_identifier(node)

        def _sig(node) -> str:
            t = _text(node)
            return (t.splitlines()[0].strip()[:200] if t else node.type)

        def _refs(node) -> Set[str]:
            out: Set[str] = set()
            stack = list(node.children)
            while stack:
                c = stack.pop()
                if "call" in c.type or "invocation" in c.type:
                    for cc in c.children:
                        if "identifier" in cc.type:
                            out.add(_text(cc))
                            break
                stack.extend(c.children)
            return out

        def walk(node, stack: List[str]) -> None:
            for c in node.children:
                kind = _DEF_KIND.get(c.type)
                if kind:
                    name = _name(c)
                    if name:
                        node_id = f"{path}::{'.'.join([*stack, name])}"
                        k = "method" if (kind == "def" and stack) else kind
                        symbols.append(Symbol(node_id, name, k, path, c.start_point[0] + 1, _sig(c)))
                        for r in _refs(c):
                            refs.append((node_id, r))
                        walk(c, [*stack, name])
                        continue
                walk(c, stack)

        walk(tree.root_node, [])
        return symbols, refs


def treesitter_extractors() -> List[TreeSitterExtractor]:
    """One extractor per language, each owning its extensions. Empty if the extra isn't installed."""
    if not available():
        return []
    by_lang = defaultdict(list)
    for ext, lang in _LANG_BY_EXT.items():
        by_lang[lang].append(ext)
    return [TreeSitterExtractor(lang, tuple(exts)) for lang, exts in by_lang.items()]
