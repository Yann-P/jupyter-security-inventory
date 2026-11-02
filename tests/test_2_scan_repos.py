"""Tests for scripts/2_scan_repos.py."""

import importlib

scan = importlib.import_module("2_scan_repos")

WORKFLOW = """
on: [push, pull_request_target]
jobs:
  release:  # a job, not a trigger
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_TOKEN }}
          token: ${{ secrets.GITHUB_TOKEN }}
"""


def test_declared_package_skips_private_packages_and_templates():
    assert scan.declared_package("pyproject.toml", '[project]\nname = "jupyterhub"')["name"] == "jupyterhub"
    assert scan.declared_package("package.json", '{"name": "demo", "private": true}') is None
    assert scan.declared_package("setup.py", 'setup(name="{{ cookiecutter.name }}")') is None


def test_summarize_workflows_finds_triggers_secrets_and_publishing():
    assert scan.summarize_workflows([WORKFLOW]) == {
        "count": 1,
        "triggers": ["pull_request_target", "push"],
        "secrets": ["PYPI_TOKEN"],  # GITHUB_TOKEN is left out: every repo has it
        "publishes": ["pypi"],
    }


def test_chartpress_images_are_the_prefix_and_the_name_of_each_image():
    chartpress = """
charts:
  - name: jupyterhub
    imagePrefix: quay.io/jupyterhub/k8s-
    images:
      hub:
        contextPath: images/hub
      awaiter:
        imageName: quay.io/jupyterhub/k8s-image-awaiter  # an explicit name wins
  - name: no-images
"""
    assert scan.chartpress_images(chartpress) == ["quay.io/jupyterhub/k8s-hub", "quay.io/jupyterhub/k8s-image-awaiter"]
    assert scan.chartpress_images("not: [valid") == []


def test_chartpress_images_ignores_a_file_that_is_not_shaped_like_a_chartpress_file():
    for text in ("", "- hub", "charts:", "charts: [hub]", "charts: [{images: [hub]}]"):  # "" is what a symlink reads as
        assert scan.chartpress_images(text) == []


def test_mentions_lists_the_files_that_mention_a_word_and_ignores_comments():
    files = {
        ".github/workflows/lint.yml": "steps:\n  - run: uvx zizmor .\n  - run: pre-commit run -a",
        ".github/workflows/ci.yml": "steps:\n  - uses: zizmorcore/zizmor-action@abc123  # v1",
        ".github/workflows/test.yml": "# zizmor is great\non: push  # zizmor: ignore[dangerous-triggers]\nsteps: []",
    }
    assert scan.mentions(files) == {
        "zizmor": [".github/workflows/ci.yml", ".github/workflows/lint.yml"],  # test.yml only has comments
        "zizmor-action": [".github/workflows/ci.yml"],
        "pre-commit": [".github/workflows/lint.yml"],
    }
    assert scan.mentions({"a.yml": "name: Zizmor"}) == {"zizmor": ["a.yml"]}  # any case; the other words are left out
    assert scan.mentions({"a.yml": "url: https://example.org/page#zizmor"}) == {"zizmor": ["a.yml"]}  # not a comment


def test_pre_commit_summary_lists_hook_sources_and_ids_and_whether_precommit_ci_is_set_up():
    config = """
ci:
  autoupdate_schedule: monthly
repos:
  - repo: https://github.com/zizmorcore/zizmor-pre-commit
    rev: v1.0.0
    hooks:
      - id: zizmor
  - repo: local
    hooks:
      - id: mine
"""
    assert scan.pre_commit_summary(config) == {
        "repos": ["https://github.com/zizmorcore/zizmor-pre-commit"],  # "local" is not a place to read hooks from
        "hooks": ["mine", "zizmor"],
        "ci": True,
    }
    assert scan.pre_commit_summary("repos: []") == {"repos": [], "hooks": [], "ci": False}


def test_pre_commit_summary_survives_a_file_that_is_not_shaped_like_a_config():
    empty = {"repos": [], "hooks": [], "ci": False}
    for text in (
        "",
        "- hooks",
        "repos: oops",
        "repos: [oops]",
        "repos: [{hooks: []}]",
        "not: [valid",
    ):  # "" is a symlink
        assert scan.pre_commit_summary(text) == empty


def test_only_the_files_that_are_read_are_downloaded():
    assert scan.worth_reading(".pre-commit-config.yaml")
    assert not scan.worth_reading("docs/.pre-commit-config.yaml")  # only the repo's own config counts
    assert scan.worth_reading(".github/workflows/zizmor.yml")
