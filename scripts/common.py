"""Helpers shared by the scripts."""

import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import urllib3

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"  # every file the scripts write
CACHE = ROOT / ".cache" / "http"
CACHE_HOURS = 24  # cached answers older than this are downloaded again, so counts stay current
RETRY_ON = {429, 500, 502, 503, 504}  # HTTP errors that are worth retrying: rate limits, server hiccups


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_json(url: str, delay: float = 0.0):
    """GET a JSON URL. Returns None if it does not exist (404).

    Answers are cached in .cache/http/ for CACHE_HOURS, so running a script twice in a day does not
    download anything twice. `delay` waits before the request (not before its retries), for APIs that limit
    how often we may call them.
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
    real wait there, as a Unix time."""

    def get_retry_after(self, response):
        waits = [super().get_retry_after(response) or 0]
        reset = response.headers.get("X-RateLimit-Reset", "")
        # Only a refusal waits for the reset: pypistats.org sends the header on every answer, its errors too.
        if response.status == 429 and reset.strip().isdigit():
            waits.append(float(reset) - time.time())
        return min(max(waits), self.retry_after_max) or None  # None: no wait asked, so urllib3 backs off on its own


# One pool of connections per site, shared by all threads: reusing connections saves a TLS handshake per request.
HTTP = urllib3.PoolManager(
    maxsize=16,  # connections kept open per site: one per thread of the largest pool in step 3
    headers={"User-Agent": "jupyter-security-inventory"},
    timeout=60,
    # Waits 0, 4, 8, 16, 32 s between the attempts: npm's download API refuses without saying for how long, over a
    # minute-long window. If the server asks, waits that long instead, up to 5 minutes.
    retries=Retry(total=5, backoff_factor=2, backoff_max=60, retry_after_max=300, status_forcelist=RETRY_ON),
)


def download_json(url: str, delay: float):
    time.sleep(delay)
    response = HTTP.request("GET", url)  # raises MaxRetryError when the retries run out
    retried = [attempt for attempt in response.retries.history if attempt.redirect_location is None]
    if retried:
        print(f"{len(retried)} retries: {url}", file=sys.stderr, flush=True)
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
