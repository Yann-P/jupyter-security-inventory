"""Tests for scripts/topics/owner.py."""

from topics import owner


def test_an_owner_of_none_is_flagged_like_no_owner():
    assert owner.check({"owner": "None"}, {}).status == owner.check({"owner": None}, {}).status == "missing"
    assert owner.check({"owner": "jupyterhub-council"}, {}).status == "done"
