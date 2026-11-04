"""Tests for scripts/topics/npm_trusted_publishing.py."""

from topics import npm_trusted_publishing


def status(*packages):
    repo = {
        "packages": [
            {"system": "NPM", "name": n, "latest_published": day, "trusted_publishing": tp} for n, day, tp in packages
        ]
    }
    return npm_trusted_publishing.check(repo, {}).status


def test_only_packages_released_since_trusted_publishing_began_count():
    assert status(("a", "2026-01-01", True), ("old", "2024-01-01", False)) == "done"
    assert status(("a", "2026-01-01", True), ("b", None, False)) == "partial"
    assert status(("old", "2024-01-01", False)) == "n/a"
