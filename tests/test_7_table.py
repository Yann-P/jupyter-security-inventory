"""Tests for scripts/7_table.py."""

import importlib

table = importlib.import_module("7_table")


def repo(**changes):
    """A repo record as step 6 writes it, with no package and nobody using it."""
    record = {
        "full_name": "o/r",
        "top_package": None,
        "images": [],
        "used_by": {"ci": [], "build": [], "ci_pinned": []},
        "classification": {"kind": "tooling", "deploys_live_service": None, "security_boundary": None},
    }
    return record | changes


def test_used_in_ci_counts_each_repo_once_and_skips_sha_pinned_ones():
    row = table.row(repo(used_by={"ci": ["a", "b"], "build": ["a"], "ci_pinned": ["c"]}))
    assert row["used in CI"] == 2


def test_columns_stay_empty_rather_than_zero_or_no():
    row = table.row(repo())
    assert (row["downloads/month"], row["images"], row["used in CI"], row["security boundary"]) == ("", "", "", "")
