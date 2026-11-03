"""Tests for scripts/topics/security_policy.py."""

from topics import security_policy

ORG = {"path": "SECURITY.md", "emails": ["security@ipython.org"]}


def status(own):
    repo = {"full_name": "jupyter/a", "org": "jupyter", "packages": [{}], "images": []}
    scan = {"jupyter/a": {"security_policy": own}, "jupyter/.github": {"security_policy": ORG}}
    return security_policy.check(repo, scan).status


def test_a_policy_of_its_own_matters_only_if_it_lists_other_emails():
    assert status(None) == status(ORG) == "done"
    assert status({"path": "SECURITY.md", "emails": ["me@example.com"]}) == "partial"
