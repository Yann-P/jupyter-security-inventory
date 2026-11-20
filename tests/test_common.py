"""Tests for scripts/common.py."""

import time

import common
import urllib3
from common import github_repos_in, pep503


def test_pep503_gives_the_name_pypi_uses():
    assert pep503("Jupyter_Core") == "jupyter-core"
    assert pep503("jupyter.server--proxy") == "jupyter-server-proxy"


def test_github_repos_in_finds_https_and_ssh_links():
    text = "Code: https://github.com/jupyter/Notebook.git, mirror: git@github.com:ipython/ipython"
    assert github_repos_in(text) == {"jupyter/notebook", "ipython/ipython"}


def test_only_a_rate_limit_refusal_waits_for_the_reset():
    retry = common.HTTP.connection_pool_kw["retries"]

    def wait(status, reset_in):
        headers = {"Retry-After": "0", "X-RateLimit-Reset": str(int(time.time()) + reset_in)}
        return retry.get_retry_after(urllib3.HTTPResponse(status=status, headers=headers))

    assert 1 < wait(429, 3) <= 3
    assert wait(429, 3600) == retry.retry_after_max
    assert wait(503, 3) is None
