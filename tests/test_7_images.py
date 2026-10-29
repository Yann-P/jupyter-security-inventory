"""Tests for scripts/7_images.py."""

import importlib

images = importlib.import_module("7_images")

REPO_NAMES = {"jupyter/docker-stacks": "jupyter/docker-stacks", "jupyterhub/jupyterhub": "jupyterhub/jupyterhub"}
HUB = "https://hub.docker.com/v2/repositories/jupyterhub/hub/tags"
QUAY = "https://quay.io/api/v1/repository/jupyter/stack/tag/?limit=1&onlyActiveTags=true"


def stub_registry(monkeypatch, answers):
    """Make fetch_json answer from a {url: body} dict; any other URL is a 404."""
    monkeypatch.setattr(images, "fetch_json", lambda url: answers.get(url))


def test_linked_repos_prefers_the_link_then_the_repo_named_like_the_image():
    linked = images.linked_repos
    assert linked("jupyter", "base-notebook", "See <https://github.com/Jupyter/docker-stacks>", REPO_NAMES) == [
        "jupyter/docker-stacks"
    ]
    assert linked("jupyterhub", "jupyterhub", "JupyterHub: multi-user server", REPO_NAMES) == ["jupyterhub/jupyterhub"]
    assert linked("jupyterhub", "k8s-hub", None, REPO_NAMES) == []  # nothing says where it is built
    assert linked("jupyter", "x", "https://github.com/someone/else", REPO_NAMES) == []  # not in the inventory


def test_first_line_turns_a_readme_into_a_description():
    assert images.first_line("# Base Jupyter Notebook Stack\n\nGitHub Actions builds this image.") == (
        "Base Jupyter Notebook Stack"
    )
    assert images.first_line("") is None


def test_hub_image_pulls_latest_and_falls_back_to_the_newest_tag(monkeypatch):
    repo = {"name": "hub", "pull_count": 7, "description": ""}
    latest = {"name": "latest", "digest": "sha256:a", "tag_last_pushed": "2026-10-28T10:05:15Z"}
    stub_registry(monkeypatch, {f"{HUB}/latest": latest})
    image = images.hub_image("jupyterhub", repo, REPO_NAMES)
    assert image["reference"] == "docker.io/jupyterhub/hub:latest"
    assert (image["digest"], image["last_pushed"], image["pulls"], image["description"]) == (
        "sha256:a",
        "2026-10-28",
        7,
        None,
    )

    newest = {"name": "5.0.0-dev", "last_updated": "2026-10-21T00:00:00Z", "images": [{"digest": "sha256:b"}]}
    stub_registry(monkeypatch, {f"{HUB}?page_size=1": {"results": [newest]}})
    image = images.hub_image("jupyterhub", repo, REPO_NAMES)
    assert image["reference"] == "docker.io/jupyterhub/hub:5.0.0-dev"
    assert image["digest"] == "sha256:b"  # a single-platform image: the digest of its one build

    stub_registry(monkeypatch, {f"{HUB}?page_size=1": {"results": []}})
    assert images.hub_image("jupyterhub", repo, REPO_NAMES) is None  # nothing to pull


def test_quay_image_pulls_latest_and_falls_back_to_the_newest_tag(monkeypatch):
    repo = {"name": "stack", "description": "# A stack\n\nBuilt by https://github.com/jupyter/docker-stacks"}
    tag = {"name": "latest", "manifest_digest": "sha256:c", "start_ts": 1793224803}
    stub_registry(monkeypatch, {f"{QUAY}&specificTag=latest": {"tags": [tag]}})
    image = images.quay_image("jupyter", repo, REPO_NAMES)
    assert image["reference"] == "quay.io/jupyter/stack:latest"
    assert (image["digest"], image["last_pushed"], image["pulls"], image["repos"]) == (
        "sha256:c",
        "2026-10-28",
        None,  # Quay publishes no pull counts
        ["jupyter/docker-stacks"],
    )

    stub_registry(monkeypatch, {f"{QUAY}&specificTag=latest": {"tags": []}, QUAY: {"tags": [{**tag, "name": "1.0"}]}})
    assert images.quay_image("jupyter", repo, REPO_NAMES)["reference"] == "quay.io/jupyter/stack:1.0"

    stub_registry(monkeypatch, {QUAY: {"tags": []}})
    assert images.quay_image("jupyter", repo, REPO_NAMES) is None


def test_quay_repos_follows_the_pages(monkeypatch):
    url = "https://quay.io/api/v1/repository?namespace=jupyter&public=true"
    stub_registry(
        monkeypatch,
        {
            url: {"repositories": [{"name": "a"}], "next_page": "t 1"},
            f"{url}&next_page=t%201": {"repositories": [{"name": "b"}]},
        },
    )
    assert [repo["name"] for repo in images.quay_repos("jupyter")] == ["a", "b"]


def test_export_is_one_reference_per_line():
    assert images.export([{"reference": "quay.io/jupyter/a:latest"}, {"reference": "docker.io/x/b:1"}]) == (
        "quay.io/jupyter/a:latest\ndocker.io/x/b:1\n"
    )
