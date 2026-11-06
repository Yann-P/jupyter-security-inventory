"""Tests for scripts/topics/supported_python.py."""

from topics import supported_python


def check(day, *packages):
    repo = {
        "fetched_on": day,
        "packages": [{"system": s, "name": n, "latest_published": None, "requires_python": r} for s, n, r in packages],
    }
    return supported_python.check(repo, {}).status


def test_the_oldest_python_allowed_is_what_pip_would_install_on():
    oldest = supported_python.oldest_python
    assert oldest(">=3.10.2") == oldest(">3.10") == "3.10"  # some 3.10 releases are allowed
    assert oldest(">=3.10,!=3.10.*") == "3.11"
    assert oldest(None) == oldest("") == oldest("not a specifier") == "2.6"  # pip ignores them
    assert oldest(">=3.99") is None


def test_a_python_counts_as_end_of_life_from_the_day_it_stopped_getting_security_fixes(monkeypatch):
    monkeypatch.setattr(supported_python, "END_OF_LIFE", {"3.10": "2026-10-01", "3.11": "2027-10", "3.12": "2028-10"})
    assert check("2026-09-30", ("PYPI", "a", ">=3.10")) == "done"
    assert check("2026-10-01", ("PYPI", "a", ">=3.10")) == "missing"
    assert check("2027-09-30", ("PYPI", "a", ">=3.11")) == "done"
    assert check("2027-10-01", ("PYPI", "a", ">=3.11")) == "missing"  # the table only knows the month
    assert check("2026-11-05", ("PYPI", "a", ">=3.11"), ("PYPI", "b", None), ("NPM", "c", None)) == "partial"
    assert check("2026-11-05", ("NPM", "c", None)) == "n/a"
