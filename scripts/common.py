"""Helpers shared by the scripts."""

import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"  # every file the scripts write
CACHE = ROOT / ".cache" / "http"
CACHE_HOURS = 24  # cached answers older than this are downloaded again, so counts stay current
RETRY_ON = {429, 500, 502, 503, 504}  # HTTP errors that are worth retrying: rate limits, server hiccups
_spacing = threading.Lock()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_json(url: str, delay: float = 0.0):
    """GET a JSON URL. Returns None if it does not exist (404).

    Answers are cached in .cache/http/ for CACHE_HOURS, so running a script twice in a day does not
    download anything twice. `delay` is the time between two requests, even from different threads, for APIs
    that limit how often we may call them.
    """
    cache_file = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if cache_file.exists() and time.time() - cache_file.stat().st_mtime < CACHE_HOURS * 3600:
        return json.loads(cache_file.read_text())["body"]
    body = download_json(url, delay)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"url": url, "body": body}))
    return body


def download_json(url: str, delay: float):
    request = urllib.request.Request(url, headers={"User-Agent": "jupyter-security-inventory"})
    attempts = 8
    for attempt in range(attempts):
        last_attempt = attempt == attempts - 1
        with _spacing:  # one thread sleeps at a time, so requests start `delay` apart
            time.sleep(delay)
        wait = min(2**attempt, 60)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in RETRY_ON or last_attempt:
                raise
            retry_after = error.headers.get("Retry-After", "")
            if retry_after.isdigit():  # how long the server asks us to wait
                wait = min(int(retry_after), 60)
        except urllib.error.URLError:
            if last_attempt:
                raise
        time.sleep(wait)


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
