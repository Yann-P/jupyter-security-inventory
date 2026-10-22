"""Tests for scripts/common.py."""

from common import github_repos_in, pep503


def test_pep503_gives_the_name_pypi_uses():
    assert pep503("Jupyter_Core") == "jupyter-core"
    assert pep503("jupyter.server--proxy") == "jupyter-server-proxy"


def test_github_repos_in_finds_https_and_ssh_links():
    text = "Code: https://github.com/jupyter/Notebook.git, mirror: git@github.com:ipython/ipython"
    assert github_repos_in(text) == {"jupyter/notebook", "ipython/ipython"}
