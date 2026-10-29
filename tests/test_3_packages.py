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


def test_deps_dev_gives_dependents_and_the_date_of_the_newest_version(monkeypatch):
    versions = [
        {"versionKey": {"version": "1.0"}, "publishedAt": "2024-01-02T10:00:00Z", "isDefault": False},
        {"versionKey": {"version": "2.0"}, "publishedAt": "2025-06-30T23:59:59Z", "isDefault": True},
        {"versionKey": {"version": "3.0b1"}, "publishedAt": "2026-02-01T00:00:01Z", "isDefault": False},
        {"versionKey": {"version": "0.1"}, "isDefault": False},  # no date recorded
    ]
    dependents = {"1.0": 5, "2.0": 40, "3.0b1": 7, "0.1": 1}

    def fake_fetch_json(url, delay=0.0):
        if url.endswith(":dependents"):
            return {"dependentCount": dependents[url.split("/versions/")[1].removesuffix(":dependents")]}
        return {"versions": versions} if url.endswith("/packages/some-lib") else None

    monkeypatch.setattr(packages, "fetch_json", fake_fetch_json)

    # A pre-release counts as the newest version; the default one is only used for the dependents.
    assert packages.deps_dev("PYPI", "Some_Lib") == {"dependents": 40, "last_published": "2026-02-01"}
    assert packages.deps_dev("PYPI", "unknown") == {"dependents": None, "last_published": None}
