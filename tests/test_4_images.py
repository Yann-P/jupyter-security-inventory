"""Tests for scripts/4_images.py."""

import importlib

images = importlib.import_module("4_images")

REPO_NAMES = {"jupyter/docker-stacks": "jupyter/docker-stacks", "jupyterhub/jupyterhub": "jupyterhub/jupyterhub"}


def test_source_repo_prefers_the_builder_then_the_link_then_the_repo_named_like_the_image():
    def find(namespace, name, description=None, builders=None):
        return images.source_repo(namespace, name, description, REPO_NAMES, builders or {})

    chartpress = {"jupyterhub/jupyterhub-demo": {"jupyterhub/jupyterhub"}}
    assert find("jupyterhub", "jupyterhub-demo", "see github.com/jupyter/docker-stacks", chartpress) == (
        "jupyterhub/jupyterhub",
        "built by the repo's chartpress file",
    )
    assert find("jupyter", "base-notebook", "See <https://github.com/Jupyter/docker-stacks>") == (
        "jupyter/docker-stacks",
        "linked from the registry description",
    )
    assert find("jupyterhub", "jupyterhub", "JupyterHub: multi-user server") == (
        "jupyterhub/jupyterhub",
        "named like the image",
    )
    assert find("jupyterhub", "k8s-hub") == (None, None)  # nothing says where it is built
    assert find("jupyter", "x", "https://github.com/someone/else") == (None, None)  # not in the inventory


def test_image_path_is_the_same_on_every_registry():
    assert images.image_path("quay.io/jupyterhub/k8s-hub") == "jupyterhub/k8s-hub"
    assert images.image_path("jupyterhub/mybinder.org-minesweeper") == "jupyterhub/mybinder.org-minesweeper"
