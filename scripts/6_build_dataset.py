"""Step 6: merge steps 1-5 into output/jupyter_repos.json, the file step 7 reads.

used_by lists the repos that run this repo's code:
  ci         their workflows use its actions through a tag or branch
  ci_pinned  same, but pinned to a commit SHA (a compromise does not reach them by itself)
  build      their pyproject.toml build requirements include one of its packages

Usage: python scripts/6_build_dataset.py    Output: output/jupyter_repos.json
"""

import re

from common import OUTPUT, load_json, pep503, prose_ratio, save_json


def find_users(repos: list[dict], scan: dict, packages: list[dict]) -> tuple[dict, dict]:
    """Who runs whose code.

    Returns ci_refs, {provider: {consumer: [is each reference pinned to a commit SHA?]}},
    and build_users, {provider: {consumers}}.
    """
    real_name = {repo["full_name"].lower(): repo["full_name"] for repo in repos}  # GitHub names ignore case
    publisher = {pep503(p["name"]): p["repo"] for p in packages if p["system"] == "PYPI"}
    ci_refs, build_users = {}, {}
    for repo in repos:
        consumer = repo["full_name"]
        for reference in scan[consumer]["uses"]:  # "org/repo@v1"
            target, version = reference.split("@", 1)
            provider = real_name.get(target.lower())
            if provider and provider != consumer:
                pinned = re.fullmatch(r"[0-9a-f]{40}", version) is not None
                ci_refs.setdefault(provider, {}).setdefault(consumer, []).append(pinned)
        for requirement in scan[consumer]["build_requires"]:
            provider = publisher.get(pep503(requirement))
            if provider and provider != consumer:
                build_users.setdefault(provider, set()).add(consumer)
    return ci_refs, build_users


def main():
    inventory = load_json(OUTPUT / "repos.json")
    scan = load_json(OUTPUT / "scan.json")
    packages = load_json(OUTPUT / "packages.json")["accepted"]
    images = load_json(OUTPUT / "images.json")["images"]
    labels = load_json(OUTPUT / "classification.json")
    ci_refs, build_users = find_users(inventory["repos"], scan, packages)

    records = []
    for repo in inventory["repos"]:
        name = repo["full_name"]
        mine = [p for p in packages if p["repo"] == name]
        mine.sort(key=lambda p: -(p["downloads_last_month"] or 0))
        built = sorted((i for i in images if i["repo"] == name), key=lambda i: -(i["pulls"] or 0))
        refs = ci_refs.get(name, {})
        records.append(
            {
                **repo,
                "packages": [{key: value for key, value in p.items() if key != "repo"} for p in mine],
                "images": [{key: value for key, value in i.items() if key != "repo"} for i in built],
                "top_image": f"{built[0]['registry']}/{built[0]['namespace']}/{built[0]['name']}" if built else None,
                "top_image_pulls": built[0]["pulls"] if built else None,
                "top_package": f"{mine[0]['system']}:{mine[0]['name']}" if mine else None,
                "max_downloads_last_month": max((p["downloads_last_month"] or 0 for p in mine), default=0),
                "top_package_dependents": (mine[0]["dependents"] or 0) if mine else 0,
                "content": {
                    "commit": scan[name]["head"],
                    "n_files": scan[name]["n_files"],
                    "file_types": scan[name]["file_types"],
                    "prose_ratio": prose_ratio(scan[name]["file_types"]),
                    "workflows": scan[name]["workflows"],
                },
                "used_by": {
                    "ci": sorted(consumer for consumer, pinned in refs.items() if not all(pinned)),
                    "ci_pinned": sorted(consumer for consumer, pinned in refs.items() if all(pinned)),
                    "build": sorted(build_users.get(name, set())),
                },
                "classification": labels[name],
            }
        )
    save_json(OUTPUT / "jupyter_repos.json", {"fetched_on": inventory["fetched_on"], "repos": records})
    print(f"wrote {len(records)} repos")


if __name__ == "__main__":
    main()
