# Contributing to Greenbar

Greenbar dogfoods itself — so contributing *is* using it.

## Dev setup
```bash
pip install -e ".[dev]"
pytest -q                 # the suite
greenbar gate scoped --contract contracts/CONTRACT.md   # what CI runs
```

## The bar for a change
1. Write/extend a contract in `contracts/` (or update the repo's `contracts/CONTRACT.md`).
2. `greenbar lint <contract>` must pass.
3. TDD: a failing test first, then the code. Keep the tool dependency-light (stdlib + PyYAML).
4. `greenbar gate scoped --contract contracts/CONTRACT.md` must be green before you open the PR.
5. New behavior needs a test that would fail without it.

## Design principles (don't regress these)
- **Enforced, not advisory.** Every rule should be a build failure, not a suggestion.
- **Tool-agnostic.** No coupling to one coding assistant or one CI vendor.
- **Fail closed to a clear finding.** A malformed contract yields a readable error, never a crash.
- **Dependency-light.** New runtime deps need a strong justification.

Issues and PRs welcome. Be kind; review is adversarial toward the *code*, not the author.
