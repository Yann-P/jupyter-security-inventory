"""Tests for scripts/3_packages.py."""

import importlib

packages = importlib.import_module("3_packages")


def accepted(repo, package, declared, links=(), people=""):
    entry = {"name": package, "links": links, "people": people}
    return packages.reason({"full_name": repo, "name": repo.split("/")[1]}, "PYPI", entry, declared, set()) is not None


def test_a_package_belongs_to_a_repo_only_with_evidence():
    assert accepted("jupyterhub/oauthenticator", "oauthenticator", False, ["jupyterhub/oauthenticator"])
    assert accepted(
        "jupyterlab/hatch-nodejs-version", "hatch-nodejs-version", True, ["agoose77/hatch-nodejs-version"]
    )  # moved
    assert accepted("jupyter-widgets/ipywidgets", "ipywidgets", True, people="Jupyter Development Team")
    assert not accepted("jupyter/markdown", "Markdown", False, ["python-markdown/markdown"])  # same name, other project


def test_when_two_repos_declare_a_package_the_one_the_registry_links_to_wins():
    repos = {
        "o/widget": {"full_name": "o/widget", "name": "widget"},
        "o/monorepo": {"full_name": "o/monorepo", "name": "monorepo"},
    }
    candidates = {("PYPI", "widget", "o/widget"): 1, ("PYPI", "widget", "o/monorepo"): 2}
    entries = {("PYPI", "widget"): {"name": "widget", "links": ["o/widget"], "people": "Jupyter"}}

    accepted, _ = packages.pick_publishers(candidates, entries, repos, jupyter_orgs={"o"})
    assert [p["repo"] for p in accepted] == ["o/widget"]
