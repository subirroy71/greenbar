"""Shared test isolation."""
import pytest


@pytest.fixture(autouse=True)
def _no_ambient_commit_override(monkeypatch):
    # CI's PR job exports GREENBAR_COMMIT (the PR head SHA); tests build their own repos and must
    # never inherit it, or gate history would point at a commit that doesn't exist there.
    monkeypatch.delenv("GREENBAR_COMMIT", raising=False)
