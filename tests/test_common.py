"""Tests for scripts/common.py."""

import email.message
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


def test_download_json_retries_rate_limits_when_asked_and_counts_them(monkeypatch):
    headers = email.message.Message()
    headers["Retry-After"] = "3"
    answers = [
        urllib.error.HTTPError("https://example.org/x", 429, "Too Many Requests", headers, None),
        io.BytesIO(b"1"),
    ]
    waits = []

    def urlopen(request, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(common.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(common.time, "sleep", waits.append)
    monkeypatch.setattr(common, "RETRIES", common.Counter())
    assert common.download_json("https://example.org/x", delay=0) == 1
    assert common.RETRIES == {"example.org HTTP 429": 1}
    assert 3 in waits  # the server's Retry-After, not our own 1 s


def test_retry_after_reads_seconds_and_dates():
    assert common.retry_after({"Retry-After": "120"}) == 120
    assert common.retry_after({"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}) == 0  # in the past
    assert common.retry_after({"Retry-After": "soon"}) is None
    assert common.retry_after(None) is None
