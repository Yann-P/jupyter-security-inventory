"""Tests for scripts/topics/pypi_attestations.py."""

from topics import pypi_attestations


def status(*packages):
    repo = {
        "packages": [{"system": "PYPI", "name": n, "latest_published": day, "attested": a} for n, day, a in packages]
    }
    return pypi_attestations.check(repo, {}).status


def test_only_packages_released_since_attestations_began_count():
    assert status(("a", "2026-01-01", True), ("old", "2023-01-01", False)) == "done"
    assert status(("a", "2026-01-01", True), ("b", None, False)) == "partial"
    assert status(("old", "2023-01-01", False)) == "n/a"
