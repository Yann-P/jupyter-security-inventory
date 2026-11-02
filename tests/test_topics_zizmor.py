"""Tests for scripts/topics/zizmor.py."""

from topics import zizmor

HOOK = ".pre-commit-config.yaml"
WORKFLOW = ".github/workflows/zizmor.yml"


def status(mentions, workflows=1):
    return zizmor.check({"workflows": {"count": workflows}, "mentions": mentions}).status


def test_each_way_of_running_zizmor_is_told_apart():
    assert status({"zizmor": [WORKFLOW], "zizmor-action": [WORKFLOW]}) == "done"  # the GitHub Action
    assert status({"zizmor": [WORKFLOW]}) == "done"  # a command in a workflow
    assert status({"zizmor": [HOOK], "pre-commit": ["lint.yml"]}) == "done"  # a hook that CI runs
    assert status({"zizmor": [HOOK]}) == "partial"  # a hook nothing runs in CI
    assert status({"pre-commit": ["lint.yml"]}) == "missing"
    assert status({"zizmor": [HOOK]}, workflows=0) == "n/a"  # nothing to check


def test_the_result_says_how_and_shows_the_files():
    result = zizmor.check(
        {"workflows": {"count": 1}, "mentions": {"zizmor": [HOOK, WORKFLOW], "zizmor-action": [WORKFLOW]}}
    )
    assert (result.via, result.evidence) == (["GitHub Action", "pre-commit"], [HOOK, WORKFLOW])
