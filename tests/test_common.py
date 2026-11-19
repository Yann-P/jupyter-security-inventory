"""Tests for scripts/common.py."""

import io
import urllib.error

import common
from common import github_repos_in, pep503


def test_pep503_gives_the_name_pypi_uses():
    assert pep503("Jupyter_Core") == "jupyter-core"
    assert pep503("jupyter.server--proxy") == "jupyter-server-proxy"


def test_github_repos_in_finds_https_and_ssh_links():
    text = "Code: https://github.com/jupyter/Notebook.git, mirror: git@github.com:ipython/ipython"
    assert github_repos_in(text) == {"jupyter/notebook", "ipython/ipython"}


def test_download_json_retries_rate_limits_and_counts_them(monkeypatch):
    answers = [urllib.error.HTTPError("https://example.org/x", 429, "Too Many Requests", None, None), io.BytesIO(b"1")]

    def urlopen(request, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(common.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(common.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(common, "RETRIES", common.Counter())
    assert common.download_json("https://example.org/x", delay=0) == 1
    assert common.RETRIES == {"example.org HTTP 429": 1}
