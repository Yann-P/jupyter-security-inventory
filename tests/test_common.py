"""Tests for scripts/common.py."""

import io
import json
import urllib.error

import common
import pytest
from common import download_json, github_repos_in, pep503


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Record the sleeps instead of sleeping, and forget which hosts were called."""
    sleeps = []
    monkeypatch.setattr(common.time, "sleep", sleeps.append)
    monkeypatch.setattr(common, "_next_turn", {})
    return sleeps


def fake_urlopen(monkeypatch, *answers):
    """Make urlopen return (or raise) `answers` one after the other."""
    answers = list(answers)

    def urlopen(request, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(json.dumps(answer).encode())

    monkeypatch.setattr(common.urllib.request, "urlopen", urlopen)


def http_error(code, **headers):
    return urllib.error.HTTPError("https://example.org/x", code, "error", headers, None)


def test_download_json_waits_as_long_as_retry_after_says(monkeypatch, no_waiting):
    fake_urlopen(monkeypatch, http_error(429, **{"Retry-After": "7"}), {"ok": True})
    assert download_json("https://example.org/x", delay=0) == {"ok": True}
    assert no_waiting[-1] == pytest.approx(7, abs=0.5)


def test_download_json_backs_off_without_retry_after_and_gives_up_in_the_end(monkeypatch, no_waiting):
    fake_urlopen(monkeypatch, *[http_error(429)] * common.ATTEMPTS)
    with pytest.raises(urllib.error.HTTPError):
        download_json("https://example.org/x", delay=0)
    assert [round(s) for s in no_waiting if s > 0.5] == [1, 2, 4, 8, 16, 32, 60]


def test_download_json_returns_none_for_404_without_retrying(monkeypatch, no_waiting):
    fake_urlopen(monkeypatch, http_error(404))
    assert download_json("https://example.org/x", delay=0) is None


def test_a_rate_limited_host_makes_other_threads_wait_too(monkeypatch, no_waiting):
    fake_urlopen(monkeypatch, http_error(429, **{"Retry-After": "30"}), {})
    download_json("https://example.org/x", delay=0)
    no_waiting.clear()
    common.wait_turn("example.org", 0)  # a second thread that arrives while the first one is holding off
    assert no_waiting[0] > 25


def test_wait_turn_spaces_requests_to_one_host_apart(no_waiting):
    for _ in range(3):
        common.wait_turn("example.org", 0.2)
    common.wait_turn("other.org", 0.2)
    assert no_waiting[0] == pytest.approx(0, abs=0.05)
    assert no_waiting[1] == pytest.approx(0.2, abs=0.05)
    assert no_waiting[2] == pytest.approx(0.4, abs=0.05)
    assert no_waiting[3] == pytest.approx(0, abs=0.05)


def test_pep503_gives_the_name_pypi_uses():
    assert pep503("Jupyter_Core") == "jupyter-core"
    assert pep503("jupyter.server--proxy") == "jupyter-server-proxy"


def test_github_repos_in_finds_https_and_ssh_links():
    text = "Code: https://github.com/jupyter/Notebook.git, mirror: git@github.com:ipython/ipython"
    assert github_repos_in(text) == {"jupyter/notebook", "ipython/ipython"}
