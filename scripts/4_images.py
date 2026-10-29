"""Step 4: the container images that Jupyter publishes on Docker Hub and Quay.

For each image: the tag people pull (`latest`, or the newest tag if there is no `latest`), when it was published,
its Docker Hub pull count (all time) and the repo it comes from, with the reason. The repo is the first match of: the
repo whose chartpress file builds the image (step 2), a repo the registry description links to, the repo named like
the image. Forks never match. Images with no tag are left out.

Also writes output/images.txt: one image reference per line.

Limits: ghcr.io cannot list a namespace without authentication, so it is not covered. Quay has no pull counts.

Usage: python scripts/4_images.py    Needs: output/repos.json (step 1) and output/scan.json (step 2)
Output: output/images.json, output/images.txt
"""

import datetime
from concurrent.futures import ThreadPoolExecutor

from common import OUTPUT, fetch_json, github_repos_in, load_json, quote, save_json

# The registry namespaces of Project Jupyter, written by hand like ORGS in step 1. Each must be a GitHub organization
# with repos in the inventory: the site uses it as the organization of the image. Check a namespace before adding it:
# on Docker Hub, `jupytercon` holds throwaway images built for conference tutorials, and `binder` and `voila` are not
# Jupyter's.
NAMESPACES = {
    "docker.io": ["ipython", "jupyter", "jupyterhub"],
    "quay.io": ["jupyter", "jupyterhealth", "jupyterhub"],
}


def image_path(ref: str) -> str:
    """'quay.io/jupyterhub/k8s-hub' -> 'jupyterhub/k8s-hub': the name of an image, whatever its registry."""
    first, _, rest = ref.partition("/")
    return (rest if "." in first or ":" in first else ref).lower()


def source_repo(namespace: str, name: str, description: str | None, repo_names: dict, builders: dict) -> tuple:
    """(repo, reason) for the repo an image comes from, or (None, None).

    `repo_names` maps lower-case 'org/repo' to the real name, because GitHub names ignore case. `builders` maps
    an image's lower-case path to the lower-case repos whose chartpress files build it. If several repos fit the
    same reason, the first by name wins.
    """
    path = f"{namespace}/{name}".lower()
    evidence = (
        ("built by the repo's chartpress file", builders.get(path, set())),
        ("linked from the registry description", github_repos_in(description)),
        ("named like the image", {path}),
    )
    for reason, repos in evidence:
        found = repos & repo_names.keys()
        if found:
            return repo_names[min(found)], reason
    return None, None


def hub_repos(namespace: str) -> list[dict]:
    url, found = f"https://hub.docker.com/v2/namespaces/{quote(namespace)}/repositories?page_size=100", []
    while url:
        page = fetch_json(url)
        found += page["results"]
        url = page["next"]
    return found


def hub_image(namespace: str, repo: dict) -> dict | None:
    """What Docker Hub says about one image, or None if it has no tag."""
    name = repo["name"]
    tags = f"https://hub.docker.com/v2/repositories/{quote(namespace)}/{quote(name)}/tags"
    tag = fetch_json(f"{tags}/latest")
    if tag is None:  # the API lists the newest tag first
        newest = (fetch_json(f"{tags}?page_size=1") or {}).get("results")
        tag = newest[0] if newest else None
    if tag is None:
        return None
    return {
        "registry": "docker.io",
        "namespace": namespace,
        "name": name,
        "tag": tag["name"],
        "last_published": (tag.get("tag_last_pushed") or tag["last_updated"])[:10],
        "pulls": repo["pull_count"],
        "description": repo["description"],
    }


def quay_repos(namespace: str) -> list[dict]:
    url, found, token = f"https://quay.io/api/v1/repository?namespace={quote(namespace)}&public=true", [], None
    while True:
        page = fetch_json(url + (f"&next_page={quote(token)}" if token else ""))
        found += page["repositories"]
        token = page.get("next_page")
        if not token:
            return found


def quay_image(namespace: str, repo: dict) -> dict | None:
    """What Quay says about one image, or None if it has no tag."""
    name = repo["name"]
    tags = f"https://quay.io/api/v1/repository/{quote(namespace)}/{quote(name)}/tag/?limit=1&onlyActiveTags=true"
    # without specificTag, the API lists the newest tag first
    for url in (f"{tags}&specificTag=latest", tags):
        found = (fetch_json(url) or {}).get("tags")
        if found:
            break
    else:
        return None
    tag = found[0]
    return {
        "registry": "quay.io",
        "namespace": namespace,
        "name": name,
        "tag": tag["name"],
        "last_published": datetime.datetime.fromtimestamp(tag["start_ts"], datetime.UTC).date().isoformat(),
        "pulls": None,
        "description": repo.get("description"),
    }


READERS = {"docker.io": (hub_repos, hub_image), "quay.io": (quay_repos, quay_image)}  # list the repos, read an image


def main():
    inventory = load_json(OUTPUT / "repos.json")
    scan = load_json(OUTPUT / "scan.json")
    orgs = {repo["org"] for repo in inventory["repos"]}
    unknown = {ns for namespaces in NAMESPACES.values() for ns in namespaces} - orgs
    if unknown:
        raise SystemExit(f"NAMESPACES has {sorted(unknown)}, which have no repo in the inventory (step 1)")

    # Forks are skipped, as in step 3: a fork has the chartpress file of its original, but does not build the image.
    repo_names = {repo["full_name"].lower(): repo["full_name"] for repo in inventory["repos"] if not repo["is_fork"]}
    builders = {}
    for repo, found in scan.items():
        for ref in found["images"]:
            builders.setdefault(image_path(ref), set()).add(repo.lower())

    jobs = []
    for registry, namespaces in NAMESPACES.items():
        list_repos, get_image = READERS[registry]
        for namespace in namespaces:
            jobs += [(get_image, namespace, repo) for repo in list_repos(namespace)]
    with ThreadPoolExecutor(4) as pool:
        found = list(filter(None, pool.map(lambda job: job[0](job[1], job[2]), jobs)))

    images = []
    for image in sorted(found, key=lambda i: (i["registry"], i["namespace"], i["name"])):
        description = image.pop("description")
        repo, reason = source_repo(image["namespace"], image["name"], description, repo_names, builders)
        reference = f"{image['registry']}/{image['namespace']}/{image['name']}:{image['tag']}"
        images.append({**image, "reference": reference, "repo": repo, "reason": reason})

    save_json(OUTPUT / "images.json", {"images": images})
    (OUTPUT / "images.txt").write_text("".join(image["reference"] + "\n" for image in images), encoding="utf-8")
    print(f"{len(images)} images from {len(jobs)} repositories in {sum(map(len, NAMESPACES.values()))} namespaces")


if __name__ == "__main__":
    main()
