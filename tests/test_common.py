"""Tests for scripts/common.py."""

import http.server
import threading
import time

import common
import pytest
import urllib3
from common import github_repos_in, pep503


def test_pep503_gives_the_name_pypi_uses():
    assert pep503("Jupyter_Core") == "jupyter-core"
    assert pep503("jupyter.server--proxy") == "jupyter-server-proxy"


def test_github_repos_in_finds_https_and_ssh_links():
    text = "Code: https://github.com/jupyter/Notebook.git, mirror: git@github.com:ipython/ipython"
    assert github_repos_in(text) == {"jupyter/notebook", "ipython/ipython"}


def test_download_json_waits_for_a_rate_limit_reset_and_counts_the_retries(monkeypatch):
    # A local server like pypistats.org: rate-limit headers on every answer. /limited refuses once with
    # "Retry-After: 0" and a reset 2 to 3 s away; /down always fails.
    class Handler(http.server.BaseHTTPRequestHandler):
        requests = 0

        def do_GET(self):
            Handler.requests += 1
            if self.path == "/down" or Handler.requests == 1:
                self.send_response(503 if self.path == "/down" else 429)
                self.send_header("Retry-After", "0")
                self.send_header("X-RateLimit-Reset", str(int(time.time()) + 3))
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"1")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    waits = []
    monkeypatch.setattr(time, "sleep", waits.append)
    monkeypatch.setattr(common, "RETRIES", common.Counter())
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        assert common.download_json(f"{url}/limited", delay=0) == 1
        assert any(1 < wait <= 3 for wait in waits)  # until the reset, not urllib3's immediate first retry
        waits.clear()
        with pytest.raises(urllib3.exceptions.MaxRetryError):
            common.download_json(f"{url}/down", delay=0)
        assert waits == [0, 4, 8, 16, 32]  # a server error backs off, whatever the rate-limit headers say
    finally:
        server.shutdown()
        server.server_close()
    assert common.RETRIES == {"127.0.0.1 HTTP 429": 1, "127.0.0.1 HTTP 503": 5}  # 6 attempts are 5 retries
