"""Step 3: which PyPI/npm packages each repo publishes, with downloads and dependents.

Candidates: the packages a repo's manifests declare, plus a package named like the repo.
The PyPI/npm entry must confirm a candidate (see `reason`). Forks are skipped. If several
repos qualify, the one the registry links to wins, then the one declaring it in the
shallowest folder (deeper copies are usually stubs or vendored).

Downloads: pypistats.org (last 30 days) and api.npmjs.org (last month).
Dependents: deps.dev, largest count over the default and 12 newest versions.
Last published: the date of the newest version on deps.dev.

Usage: python scripts/3_packages.py    Output: output/packages.json
"""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath

from common import OUTPUT, fetch_json, github_repos_in, load_json, pep503, quote, save_json


def registry_entry(system: str, name: str) -> dict | None:
    """What PyPI or npm says about a package: its exact name, the GitHub repos it links to, and its
    authors and maintainers. None if the package does not exist."""
    if system == "PYPI":
        body = fetch_json(f"https://pypi.org/pypi/{quote(name)}/json")
        if body is None:
            return None
        info = body["info"]
        urls = [info.get("home_page"), info.get("download_url"), *(info.get("project_urls") or {}).values()]
        people = [info.get(key) or "" for key in ("author", "author_email", "maintainer", "maintainer_email")]
        name = info["name"]
    else:
        body = fetch_json(f"https://registry.npmjs.org/{quote(name)}/latest", delay=2)  # 8 threads: ~4 requests/s
        if not isinstance(body, dict) or "version" not in body:
            return None
        repository = body.get("repository")
        urls = [repository.get("url") if isinstance(repository, dict) else repository, body.get("homepage")]
        people = [str(body.get("author") or "")] + [str(m) for m in body.get("maintainers") or []]
        name = body.get("name", name)
    links = set()
    for url in urls:
        if isinstance(url, str):
            links |= github_repos_in(url)
    return {"name": name, "links": sorted(links), "people": " ".join(people)}


def reason(repo: dict, system: str, entry: dict, declared: bool, jupyter_orgs: set) -> str | None:
    """Why the registry confirms that `repo` publishes this package, or None.

    `declared` is True when one of the repo's manifests declares the package, False when the
    package is only a guess from the repo's name.
    """
    links = entry["links"]
    package = pep503(entry["name"].split("/")[-1] if system == "NPM" else entry["name"])  # "@scope/name" -> "name"
    repo_name = pep503(repo["name"])
    names_match = package.startswith(repo_name) or package.endswith(repo_name) or repo_name.startswith(package)
    links_here = repo["full_name"].lower() in links
    links_same_name = any(link.split("/")[1] == repo["name"].lower() for link in links)
    jupyter_owned = (
        any(link.split("/")[0] in jupyter_orgs for link in links)
        or re.search(r"jupyter|ipython", entry["people"], re.I) is not None
    )

    if links_here and (declared or names_match):
        return "registry links to this repo"
    if declared and links_same_name:
        return "declared here; registry links to a same-named repo (this repo's former home)"
    if declared and jupyter_owned:
        return "declared here; registry entry is Jupyter-owned"
    if declared and names_match and not links:
        return "declared here under the repo's own name; registry has no conflicting link"
    return None


def downloads(system: str, name: str) -> int | None:
    if system == "PYPI":
        body = fetch_json(f"https://pypistats.org/api/packages/{quote(pep503(name))}/recent", delay=1.1)
        return body["data"]["last_month"] if body else None
    body = fetch_json(f"https://api.npmjs.org/downloads/point/last-month/{quote(name)}")
    return body["downloads"] if body else None


def deps_dev(system: str, name: str) -> dict | None:
    """What deps.dev knows about a package, or None if it does not know it.

    dependents: how many packages depend on it, the largest count over its default and 12 newest versions.
    last_published: the date of its newest version.
    """
    package = f"systems/{system.lower()}/packages/{quote(pep503(name) if system == 'PYPI' else name)}"
    info = fetch_json(f"https://api.deps.dev/v3/{package}")
    if info is None:
        return None
    versions = info["versions"]
    newest = sorted(versions, key=lambda v: v.get("publishedAt") or "")[-12:]
    default = [v for v in versions if v.get("isDefault")]
    counts = []
    for version in sorted({v["versionKey"]["version"] for v in newest + default}):
        answer = fetch_json(f"https://api.deps.dev/v3alpha/{package}/versions/{quote(version)}:dependents") or {}
        counts.append(answer.get("dependentCount", 0))
    last_published = max((v.get("publishedAt") or "" for v in versions), default="")[:10]
    return {"dependents": max(counts, default=0), "last_published": last_published or None}


def find_candidates(repos: dict, scan: dict) -> dict:
    """Packages each repo might publish.

    Returns {(system, package name, repo): depth}, where depth is how many folders deep the declaring
    manifest sits (1 = repo root), or None when the candidate is only a guess from the repo's name.
    """
    candidates = {}
    for full_name, repo in repos.items():
        if repo["is_fork"]:
            continue
        for package in scan[full_name]["packages"]:
            if package["in_test_or_example_folder"]:
                continue
            depth = len(PurePosixPath(package["path"]).parts)
            key = (package["system"], package["name"], full_name)
            candidates[key] = min(depth, candidates.get(key) or depth)
        for system in ("PYPI", "NPM"):
            candidates.setdefault((system, repo["name"].lower(), full_name), None)
    return candidates


def pick_publishers(candidates: dict, entries: dict, repos: dict, jupyter_orgs: set) -> tuple[list, list]:
    """Keep the candidates the registry confirms, and one repo per package. Returns (accepted, rejected)."""
    best = {}  # (system, package name) -> (rank, package); the lowest rank wins
    rejected = []
    for (system, name, full_name), depth in sorted(candidates.items()):
        entry = entries[(system, name)]
        if entry is None:
            continue
        why = reason(repos[full_name], system, entry, depth is not None, jupyter_orgs)
        if not why:
            rejected.append({"system": system, "name": entry["name"], "repo": full_name})
            continue
        # The repo the registry links to first, then the shallowest manifest; name guesses come last.
        rank = (full_name.lower() not in entry["links"], depth or 99)
        key = (system, entry["name"])
        if key not in best or rank < best[key][0]:
            best[key] = (rank, {"system": system, "name": entry["name"], "repo": full_name, "reason": why})
    accepted = sorted((package for _, package in best.values()), key=lambda p: (p["repo"], p["system"], p["name"]))
    return accepted, rejected


def main():
    inventory = load_json(OUTPUT / "repos.json")
    repos = {repo["full_name"]: repo for repo in inventory["repos"]}
    scan = load_json(OUTPUT / "scan.json")

    candidates = find_candidates(repos, scan)
    names = sorted({(system, name) for system, name, _ in candidates})
    with ThreadPoolExecutor(8) as pool:
        entries = dict(zip(names, pool.map(lambda key: registry_entry(*key), names)))
    packages, rejected = pick_publishers(candidates, entries, repos, set(inventory["orgs"]))

    with ThreadPoolExecutor(8) as pool:
        known = list(pool.map(lambda p: deps_dev(p["system"], p["name"]), packages))
    for package, deps in zip(packages, known):
        # One at a time, because pypistats.org limits how often we may call it.
        package["downloads_last_month"] = downloads(package["system"], package["name"])
        package["dependents"] = deps["dependents"] if deps else None
        package["last_published"] = deps["last_published"] if deps else None

    save_json(OUTPUT / "packages.json", {"accepted": packages, "rejected": rejected})
    n_repos = len({p["repo"] for p in packages})
    print(f"{len(packages)} packages from {n_repos} repos; {len(rejected)} candidates rejected")


if __name__ == "__main__":
    main()
