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
