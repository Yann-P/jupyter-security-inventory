"""Tests for scripts/common.py."""

import http.server
import threading
import time

import common
from common import github_repos_in, pep503


def test_pep503_gives_the_name_pypi_uses():
    assert pep503("Jupyter_Core") == "jupyter-core"
    assert pep503("jupyter.server--proxy") == "jupyter-server-proxy"


def test_github_repos_in_finds_https_and_ssh_links():
    text = "Code: https://github.com/jupyter/Notebook.git, mirror: git@github.com:ipython/ipython"
    assert github_repos_in(text) == {"jupyter/notebook", "ipython/ipython"}


def test_download_json_waits_for_a_rate_limit_reset_and_counts_the_retry(monkeypatch):
    # A local server that refuses the first request like pypistats.org: "Retry-After: 0" and a reset 2 s away.
    class Handler(http.server.BaseHTTPRequestHandler):
        requests = 0

        def do_GET(self):
            Handler.requests += 1
            if Handler.requests == 1:
                self.send_response(429)
                self.send_header("Retry-After", "0")
                self.send_header("X-RateLimit-Reset", str(int(time.time()) + 2))
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
    try:
        assert common.download_json(f"http://127.0.0.1:{server.server_port}/x", delay=0) == 1
    finally:
        server.shutdown()
    assert common.RETRIES == {"127.0.0.1 HTTP 429": 1}
    assert any(1 < wait <= 2 for wait in waits)  # until the reset, not urllib3's immediate first retry
