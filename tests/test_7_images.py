"""Tests for scripts/7_images.py."""

import importlib

images = importlib.import_module("7_images")

REPO_NAMES = {"jupyter/docker-stacks": "jupyter/docker-stacks", "jupyterhub/jupyterhub": "jupyterhub/jupyterhub"}


def test_linked_repos_prefers_the_link_then_the_repo_named_like_the_image():
    linked = images.linked_repos
    assert linked("jupyter", "base-notebook", "See <https://github.com/Jupyter/docker-stacks>", REPO_NAMES) == [
        "jupyter/docker-stacks"
    ]
    assert linked("jupyterhub", "jupyterhub", "JupyterHub: multi-user server", REPO_NAMES) == ["jupyterhub/jupyterhub"]
    assert linked("jupyterhub", "k8s-hub", None, REPO_NAMES) == []  # nothing says where it is built
    assert linked("jupyter", "x", "https://github.com/someone/else", REPO_NAMES) == []  # not in the inventory
