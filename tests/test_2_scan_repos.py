"""Tests for scripts/2_scan_repos.py."""

import importlib
import os
import subprocess

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


def commit(repo, filename, date):
    """Commit a new file whose commit (and author) date is `date`, whatever the machine's git settings."""
    env = {**os.environ, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date}
    for role in ("COMMITTER", "AUTHOR"):
        env |= {f"GIT_{role}_NAME": "t", f"GIT_{role}_EMAIL": "t@example.org"}
    (repo / filename).write_text(filename)
    for args in (["add", filename], ["commit", "--quiet", "-m", filename]):
        subprocess.run(["git", "-C", str(repo), *args], env=env, check=True)


def test_scan_records_the_date_of_the_latest_commit_also_when_an_earlier_clone_is_moved_forward(tmp_path):
    origin = tmp_path / "origin"
    subprocess.run(["git", "init", "--quiet", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "-C", str(origin), "config", "uploadpack.allowFilter", "true"], check=True)
    commit(origin, "README.md", "2024-03-05T12:00:00+00:00")
    # The earlier clone has the same shape as the ones step 2 makes: shallow, without file contents.
    folder = tmp_path / "clones" / "o" / "repo"
    folder.parent.mkdir(parents=True)
    clone = ["git", "clone", "--quiet", "--depth", "1", "--filter=blob:none", "--no-checkout"]
    subprocess.run([*clone, f"file://{origin}", str(folder)], check=True)

    commit(origin, "NEWS.md", "2025-11-30T12:00:00+00:00")
    result = scan.scan("o/repo", tmp_path / "clones")

    assert result["last_commit"] == "2025-11-30"
    assert result["head"] == scan.git(origin, "rev-parse", "HEAD").strip()
    assert result["n_files"] == 2
