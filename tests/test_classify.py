"""Auto blast-radius classification — glob matching, diff parsing, and the rule engine."""
from greenbar.classify import (
    DiffStat,
    classify,
    glob_to_re,
    parse_numstat,
    parse_unified_diff,
)


class TestGlob:
    def test_double_star_dir_matches_nested_and_flat(self):
        p = glob_to_re("**/migrations/**")
        assert p.match("src/db/migrations/028_add.py")
        assert p.match("migrations/1.py")
        assert not p.match("src/models/user.py")

    def test_ext_glob_matches_any_depth(self):
        p = glob_to_re("**/*.md")
        assert p.match("README.md") and p.match("docs/guide/x.md")
        assert not p.match("src/x.py")

    def test_single_star_does_not_cross_slash(self):
        assert glob_to_re("src/*.py").match("src/a.py")
        assert not glob_to_re("src/*.py").match("src/sub/a.py")

    def test_prefix_glob(self):
        assert glob_to_re("docs/**").match("docs/a/b.md")


class TestDiffParsing:
    def test_numstat(self):
        s = parse_numstat("10\t2\tsrc/a.py\n-\t-\timg.png\n5\t0\tsrc/b.py\n")
        assert set(s.files) == {"src/a.py", "img.png", "src/b.py"}
        assert s.added == 15 and s.removed == 2 and s.total_lines == 17

    def test_unified_diff(self):
        diff = (
            "diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n"
            "@@ -1 +1,2 @@\n-old\n+new1\n+new2\n"
            "diff --git a/x.md b/x.md\n--- /dev/null\n+++ b/x.md\n@@ +1 @@\n+hello\n"
        )
        s = parse_unified_diff(diff)
        assert set(s.files) == {"src/a.py", "x.md"}
        assert s.added == 3 and s.removed == 1


CFG = {
    "default": "scoped",
    "rules": [
        {"tier": "critical", "any_path": ["**/migrations/**", "**/auth/**"]},
        {"tier": "critical", "min_files": 30},
        {"tier": "trivial", "only_paths": ["**/*.md", "docs/**"]},
        {"tier": "trivial", "max_files": 1, "max_lines": 10},
        {"tier": "broken"},  # no conditions → must never match
    ],
}


class TestClassify:
    def test_sensitive_path_is_critical(self):
        tier, _ = classify(DiffStat(["src/db/migrations/028.py"], 5, 0), CFG)
        assert tier == "critical"

    def test_first_match_wins(self):
        # touches a migration (critical rule 0) AND is docs-only-ish — rule 0 wins by order
        tier, _ = classify(DiffStat(["migrations/1.py", "README.md"], 3, 1), CFG)
        assert tier == "critical"

    def test_docs_only_is_trivial(self):
        tier, _ = classify(DiffStat(["README.md", "docs/guide.md"], 20, 4), CFG)
        assert tier == "trivial"

    def test_tiny_change_is_trivial(self):
        tier, _ = classify(DiffStat(["src/a.py"], 3, 2), CFG)
        assert tier == "trivial"

    def test_big_change_is_critical(self):
        tier, _ = classify(DiffStat([f"f{i}.py" for i in range(40)], 100, 50), CFG)
        assert tier == "critical"

    def test_default_when_nothing_matches(self):
        tier, why = classify(DiffStat(["src/a.py", "src/b.py"], 200, 50), CFG)
        assert tier == "scoped" and "default" in why

    def test_conditionless_rule_never_catches(self):
        # even a change that reaches the 'broken' (no-condition) rule falls through to default
        tier, _ = classify(DiffStat(["src/a.py", "src/b.py", "src/c.py"], 300, 0), CFG)
        assert tier != "broken"
