"""Helpers shared by the scripts."""

import hashlib
import json
import re
import sys
import threading
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import urllib3

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"  # every file the scripts write
CACHE = ROOT / ".cache" / "http"
CACHE_HOURS = 24  # cached answers older than this are downloaded again, so counts stay current
RETRY_ON = {429, 500, 502, 503, 504}  # HTTP errors that are worth retrying: rate limits, server hiccups
# {"host reason": count} of the retries so far, so a step can show whether a site pushed back (retries are slow).
RETRIES = Counter()
RETRIES_LOCK = threading.Lock()


class Progress:
    """Shows "what: done/total" on one line while a script runs in a terminal. Silent in CI logs."""

    def __init__(self, what: str, total: int):
        self.what, self.total, self.done = what, total, 0
        self.lock = threading.Lock()  # ticked from several threads

    def tick(self):
        with self.lock:
            self.done += 1
            if sys.stderr.isatty():
                end = "\n" if self.done == self.total else ""
                retried = sum(RETRIES.values())
                note = f" ({retried} retries)" if retried else ""
                print(f"\r{self.what}: {self.done}/{self.total}{note}", end=end, file=sys.stderr, flush=True)

    def wrap(self, function):
        """`function`, ticking after each call."""

        def run(*args):
            result = function(*args)
            self.tick()
            return result

        return run


def retries() -> str:
    """The retries so far, by site and reason: 'registry.npmjs.org HTTP 429: 3', or 'none'."""
    with RETRIES_LOCK:
        return ", ".join(f"{key}: {count}" for key, count in sorted(RETRIES.items())) or "none"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_json(url: str, delay: float = 0.0):
    """GET a JSON URL. Returns None if it does not exist (404).

    Answers are cached in .cache/http/ for CACHE_HOURS, so running a script twice in a day does not
    download anything twice. `delay` waits before each request, for APIs that limit how often we may call them.
    """
    cache_file = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(cache_file.read_text())["body"]
    body = download_json(url, delay)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"url": url, "body": body}))
    return body


class Retry(urllib3.Retry):
    """urllib3's retries, which also wait for an X-RateLimit-Reset. pypistats.org sends "Retry-After: 0" and gives its
    real wait there, as a Unix time (like GitHub). Some APIs give the seconds left instead."""

    def get_retry_after(self, response):
        waits = [super().get_retry_after(response) or 0]
        reset = response.headers.get("X-RateLimit-Reset", "")
        # Only a refusal waits for the reset: pypistats.org sends the header on every answer, its errors too.
        if response.status == 429 and reset.strip().isdigit():
            seconds = float(reset)
            waits.append(seconds - time.time() if seconds > 1e9 else seconds)
        return min(max(waits), self.retry_after_max) or None  # None: no wait asked, so urllib3 backs off on its own

    def increment(self, method=None, url=None, response=None, error=None, _pool=None, _stacktrace=None):
        # Counted as each retry happens, not when the request ends, so a stalled run still shows what it waits for.
        host = _pool.host if _pool else "?"
        retry = super().increment(method, url, response, error, _pool, _stacktrace)  # raises when none are left
        if error is not None or response.status in self.status_forcelist:  # not a redirect
            reason = type(error).__name__ if error is not None else f"HTTP {response.status}"
            with RETRIES_LOCK:
                RETRIES[f"{host} {reason}"] += 1
        retry.host = host
        return retry

    def sleep(self, response=None):
        wait = (self.get_retry_after(response) if response is not None else None) or self.get_backoff_time()
        if wait >= 10:  # long enough to look like a stall
            print(f"\nwaiting {wait:.0f} s to retry {getattr(self, 'host', 'a site')}", file=sys.stderr, flush=True)
        super().sleep(response)


# One pool of connections per site, shared by all threads: reusing connections saves a TLS handshake per request.
HTTP = urllib3.PoolManager(
    maxsize=16,  # connections kept open per site: one per thread of the largest pool in step 3
    headers={"User-Agent": "jupyter-security-inventory"},
    timeout=60,
    # Waits 0, 4, 8, 16, 32 s between the attempts, a minute in all, so a server that refuses without saying for how
    # long (npm's download API) is waited out over a whole minute-long window. If the server asks, waits that long
    # instead, up to 5 minutes: a rate limit can ask for minutes (npm's registry asked for 212 s).
    retries=Retry(total=5, backoff_factor=2, backoff_max=60, retry_after_max=300, status_forcelist=RETRY_ON),
)


def download_json(url: str, delay: float):
    time.sleep(delay)
    response = HTTP.request("GET", url)  # raises MaxRetryError when the retries run out
    if response.status == 404:
        return None
    if response.status >= 400:
        raise urllib3.exceptions.HTTPError(f"HTTP {response.status} from {url}")
    return json.loads(response.data or b"null")


def quote(text: str) -> str:
    """Escape text for use inside a URL path: 'a/b' -> 'a%2Fb'."""
    return urllib.parse.quote(text, safe="")


def pep503(name: str) -> str:
    """The normalized form of a PyPI package name: 'Jupyter_Core' -> 'jupyter-core'."""
    return re.sub(r"[-_.]+", "-", name).lower()


def github_repos_in(text: str) -> set[str]:
    """Every GitHub repo linked in `text`, as lower-case 'org/repo'."""
    found = re.findall(r"github\.com[/:]([\w.-]+)/([\w.-]+)", text or "")
    return {f"{org}/{repo.removesuffix('.git')}".lower() for org, repo in found}


def prose_ratio(file_types: dict) -> float | None:
    """Share of docs, notebooks, web pages and media among those plus code files (None if there are none)."""
    prose = sum(file_types.get(kind, 0) for kind in ("docs", "notebook", "web", "media"))
    code = file_types.get("code", 0)
    if prose + code == 0:
        return None
    return round(prose / (prose + code), 3)
