"""Greenbar — a contract-first, gate-enforced development framework.

The thesis: most "AI dev workflows" *generate* rigor (a nice spec, a review pass) but do not
*guarantee* it — the standards are prose an operator chooses to follow. Greenbar turns the
best-practices into machine-checkable artifacts and CI gates: a change cannot merge unless its
contract validates and its tier's gates are green.

Public API is intentionally small — see `greenbar.contract`, `greenbar.config`, `greenbar.gates`.
"""

__version__ = "0.10.1"
# Rename the tool here (and in pyproject.toml [project.name] + the console-script) to rebrand.
TOOL_NAME = "greenbar"
