"""Tests for scripts/topics/pypi_attestations.py."""

from topics import pypi_attestations


def check(*packages):
    repo = {"packages": [{"system": s, "name": n, "latest_published": d, "attested": a} for s, n, d, a in packages]}
    return pypi_attestations.check(repo, {})


def test_only_pypi_packages_count_however_old():
    assert check(("PYPI", "a", "2026-01-01", True), ("NPM", "b", "2026-01-01", False)).status == "done"
    assert check(("NPM", "b", "2026-01-01", False)).status == "n/a"
    result = check(("PYPI", "a", "2026-01-01", True), ("PYPI", "old", "2018-09-25", False))
    assert (result.status, result.reason) == ("partial", "The latest release of old (2018-09-25) has no attestations.")
