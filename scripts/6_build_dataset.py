"""Step 6: join steps 1-5 into the files the web page loads, in site/data/.

    repos.json     one record per repo; ids of the packages and images it publishes and of the repos that run its code
    packages.json  one record per package; the id of the repo that publishes it
    images.json    one record per container image; the id of the repo it comes from, if any
    meta.json      when the data was fetched, and the organizations

Every cross-reference is an id (a repo's full name, a package's "SYSTEM:name", an image's "registry/namespace/name"),
so the page can follow it with one lookup. used_by and uses are the two directions of the same relation:
  ci         the workflows of the consumer use the provider's actions through a tag or branch
  ci_pinned  same, but pinned to a commit SHA (a compromise does not reach the consumer by itself)
  build      the consumer's pyproject.toml build requirements include one of the provider's packages

Usage: python scripts/6_build_dataset.py    Output: site/data/
"""

import re

from common import OUTPUT, SITE_DATA, load_json, pep503, prose_ratio, save_json


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


def package_id(package: dict) -> str:
    return f"{package['system']}:{package['name']}"


def image_id(image: dict) -> str:
    return f"{image['registry']}/{image['namespace']}/{image['name']}"


def invert(used_by: dict) -> dict:
    """{provider: {"ci": [consumers], ...}} -> {consumer: {"ci": [providers], ...}}"""
    uses = {}
    for provider, kinds in used_by.items():
        for kind, consumers in kinds.items():
            for consumer in consumers:
                uses.setdefault(consumer, {"ci": [], "ci_pinned": [], "build": []})[kind].append(provider)
    return {
        consumer: {kind: sorted(providers) for kind, providers in kinds.items()} for consumer, kinds in uses.items()
    }


def main():
    inventory = load_json(OUTPUT / "repos.json")
    scan = load_json(OUTPUT / "scan.json")
    accepted = load_json(OUTPUT / "packages.json")["accepted"]
    published = load_json(OUTPUT / "images.json")["images"]
    labels = load_json(OUTPUT / "classification.json")
    ci_refs, build_users = find_users(inventory["repos"], scan, accepted)

    packages = [
        {
            "id": package_id(p),
            "system": p["system"],
            "name": p["name"],
            "repo": p["repo"],
            "reason": p["reason"],
            "downloads_last_month": p["downloads_last_month"],
            "dependents": p["dependents"],
            "last_published": p["last_published"],  # an ISO date; None if deps.dev does not know the package
        }
        for p in sorted(accepted, key=lambda p: package_id(p).lower())
    ]

    images = [
        {
            "id": image_id(i),
            "registry": i["registry"],
            "org": i["namespace"],  # a GitHub organization, step 4 checks it
            "name": i["name"],
            "tag": i["tag"],
            "reference": i["reference"],
            "repo": i["repo"],  # None if no repo matches
            "reason": i["reason"],
            "pulls": i["pulls"],  # all time; None on Quay, which has no pull counts
            "last_published": i["last_published"],
        }
        for i in sorted(published, key=lambda i: image_id(i).lower())
    ]

    used_by = {}
    for repo in inventory["repos"]:
        name = repo["full_name"]
        refs = ci_refs.get(name, {})
        used_by[name] = {
            "ci": sorted(consumer for consumer, pinned in refs.items() if not all(pinned)),
            "ci_pinned": sorted(consumer for consumer, pinned in refs.items() if all(pinned)),
            "build": sorted(build_users.get(name, set())),
        }
    uses = invert(used_by)

    repos = []
    for repo in inventory["repos"]:
        name = repo["full_name"]
        mine = sorted((p for p in packages if p["repo"] == name), key=lambda p: -(p["downloads_last_month"] or 0))
        built = sorted((i for i in images if i["repo"] == name), key=lambda i: -(i["pulls"] or 0))
        label, content = labels[name], scan[name]
        repos.append(
            {
                "id": name,
                "org": repo["org"],
                "name": repo["name"],
                "description": repo["description"],
                "is_fork": repo["is_fork"],
                "kind": label["kind"],
                "live_service": label["deploys_live_service"],
                "security_boundary": label["security_boundary"],
                "rationale": label["rationale"],
                "packages": [p["id"] for p in mine],
                "images": [i["id"] for i in built],
                "downloads_last_month": mine[0]["downloads_last_month"] or 0 if mine else None,  # of the top package
                "dependents": mine[0]["dependents"] or 0 if mine else None,
                "pulls": built[0]["pulls"] if built else None,  # of the top image
                "used_by": used_by[name],
                "uses": uses.get(name, {"ci": [], "ci_pinned": [], "build": []}),
                "used_in_ci": len(set(used_by[name]["ci"] + used_by[name]["build"])),  # pinned ones do not count
                "workflows": content["workflows"],
                "n_files": content["n_files"],
                "file_types": content["file_types"],
                "prose_ratio": prose_ratio(content["file_types"]),
                "head": content["head"],
                "last_commit": content.get("last_commit"),  # an ISO date; None until step 2 records it
            }
        )
    repos.sort(key=lambda r: r["id"].lower())

    save_json(SITE_DATA / "repos.json", repos)
    save_json(SITE_DATA / "packages.json", packages)
    save_json(SITE_DATA / "images.json", images)
    save_json(SITE_DATA / "meta.json", {"fetched_on": inventory["fetched_on"], "orgs": inventory["orgs"]})
    print(f"wrote {len(repos)} repos, {len(packages)} packages and {len(images)} images to site/data/")


if __name__ == "__main__":
    main()
