"""Tests for scripts/topics: the answers, and the zizmor topic."""

import pytest
from topics import MISSING, NOT_APPLICABLE, STATUSES, Result, Topic, zizmor


def facts(workflows=1, mentions=None, pre_commit=None, config_files=()):
    """A repo's entry of scan.json, with just what the zizmor topic reads."""
    return {
        "workflows": {"count": workflows},
        "mentions": mentions or {},
        "pre_commit": pre_commit,
        "config_files": list(config_files),
    }


def hook(ci=False, repo="https://github.com/zizmorcore/zizmor-pre-commit"):
    return {"repos": [repo], "hooks": ["zizmor"], "ci": ci}


def test_a_result_must_have_a_known_status():
    with pytest.raises(ValueError):
        Result("great", "")


def test_a_topic_must_say_what_each_status_means():
    with pytest.raises(ValueError):
        Topic("t", "T", "?", "", {"done": "yes"}, lambda scan: Result(MISSING, ""))
    assert set(zizmor.TOPIC.meanings) == set(STATUSES)


def test_a_topic_id_is_safe_in_a_url_and_a_file_name():
    meanings = dict.fromkeys(STATUSES, "")
    for good in ("zizmor", "trusted-publishing", "python-3"):
        Topic(good, "T", "?", "", meanings, lambda scan: Result(MISSING, ""))
    for bad in ("", "Zizmor", "my topic", "a/b", "x#y", "a_b", "-a", "a--b"):
        with pytest.raises(ValueError):
            Topic(bad, "T", "?", "", meanings, lambda scan: Result(MISSING, ""))


def test_the_github_action_counts_as_running_in_ci():
    mentions = {"zizmor": [".github/workflows/zizmor.yml"], "zizmor-action": [".github/workflows/zizmor.yml"]}
    result = zizmor.check(facts(mentions=mentions))
    assert (result.status, result.via, result.evidence) == ("done", ["GitHub Action"], [".github/workflows/zizmor.yml"])


def test_a_command_in_a_workflow_counts_as_running_in_ci():
    result = zizmor.check(facts(mentions={"zizmor": [".github/workflows/lint.yml"]}))
    assert (result.status, result.via) == ("done", ["workflow command"])


def test_the_action_and_a_command_are_both_reported():
    mentions = {"zizmor": ["a.yml", "b.yml"], "zizmor-action": ["a.yml"]}
    assert zizmor.check(facts(mentions=mentions)).via == ["GitHub Action", "workflow command"]


def test_a_pre_commit_hook_is_done_when_a_workflow_runs_pre_commit():
    result = zizmor.check(facts(mentions={"pre-commit": [".github/workflows/lint.yml"]}, pre_commit=hook()))
    assert (result.status, result.via) == ("done", ["pre-commit"])
    assert result.evidence == [".github/workflows/lint.yml", ".pre-commit-config.yaml"]


def test_a_pre_commit_hook_is_done_when_the_config_sets_up_pre_commit_ci():
    result = zizmor.check(facts(pre_commit=hook(ci=True)))
    assert (result.status, result.evidence) == ("done", [".pre-commit-config.yaml"])


def test_a_pre_commit_hook_alone_is_partial():
    assert zizmor.check(facts(pre_commit=hook())).status == "partial"
    old_name = hook(repo="https://github.com/woodruffw/zizmor-pre-commit")
    assert zizmor.check(facts(pre_commit=old_name)).status == "partial"


def test_a_pre_commit_config_without_the_hook_does_not_count():
    other = {"repos": ["https://github.com/astral-sh/ruff-pre-commit"], "hooks": ["ruff"], "ci": True}
    assert zizmor.check(facts(pre_commit=other, mentions={"pre-commit": ["a.yml"]})).status == "missing"


def test_a_config_file_alone_is_partial():
    result = zizmor.check(facts(config_files=[".github/zizmor.yml"]))
    assert (result.status, result.evidence) == ("partial", [".github/zizmor.yml"])
    assert zizmor.check(facts(config_files=[".github/dependabot.yml"])).status == "missing"  # not a zizmor file


def test_workflows_and_no_sign_of_zizmor_is_missing():
    assert zizmor.check(facts()).status == MISSING


def test_no_workflows_is_not_applicable_even_with_a_hook_or_a_config_file():
    assert zizmor.check(facts(workflows=0)).status == NOT_APPLICABLE
    assert zizmor.check(facts(workflows=0, pre_commit=hook(ci=True))).status == NOT_APPLICABLE  # nothing to check
    assert zizmor.check(facts(workflows=0, config_files=["zizmor.yaml"])).status == NOT_APPLICABLE
