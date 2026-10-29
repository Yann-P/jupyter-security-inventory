"""Step 4: the container images that Jupyter publishes on Docker Hub and Quay.

For each image: the tag people pull (`latest`, or the newest tag when there is none), its digest, when it was
published, how often Docker Hub says it was pulled (all time), and the repo it comes from with the reason why.
The repo is the first of these that names an inventory repo: the one whose chartpress file builds the image
(step 2), the one its registry description links to, the one named like the image. Forks never count. Images
with no tag are left out: there is nothing to pull.

Also writes output/images.txt, one pullable reference per line, so any image scanner can read the list without
knowing this project's formats:  xargs -n1 trivy image < output/images.txt

Limits: ghcr.io cannot list a namespace without authentication, so it is not covered. Quay publishes no pull
counts. Only one tag per image is recorded; the others are older builds of the same image.

Usage: python scripts/4_images.py    Needs: output/repos.json (step 1) and output/scan.json (step 2)
Output: output/images.json, output/images.txt
"""

import datetime
from concurrent.futures import ThreadPoolExecutor

from common import OUTPUT, fetch_json, github_repos_in, load_json, quote, save_json

# The registry namespaces of Project Jupyter: the only input maintained by hand, like ORGS in step 1.
# Each is also the name of a GitHub organization of the inventory, which is how the site tells who publishes an image.
# A namespace is not always the organization's: on Docker Hub, `jupytercon` holds throwaway images built
# for conference tutorials, and `binder` and `voila` hold one image each that nothing links to Jupyter.
# So every namespace here was checked by hand.
NAMESPACES = {
    "docker.io": ["ipython", "jupyter", "jupyterhub"],
    "quay.io": ["jupyter", "jupyterhealth", "jupyterhub"],
}


def image_path(ref: str) -> str:
    """'quay.io/jupyterhub/k8s-hub' -> 'jupyterhub/k8s-hub': the name of an image, whatever its registry."""
    first, _, rest = ref.partition("/")
    return (rest if "." in first or ":" in first else ref).lower()


def first_line(text: str | None) -> str | None:
    """The first line of a description, without Markdown heading marks: Quay descriptions are whole READMEs."""
    for line in (text or "").splitlines():
        if line.strip("# \t"):
            return line.strip("# \t")
    return None


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


def describe(registry, namespace, name, tag, digest, published, pulls, description, find_repo) -> dict:
    repo, reason = find_repo(namespace, name, description)
    return {
        "registry": registry,
        "namespace": namespace,
        "name": name,
        "reference": f"{registry}/{namespace}/{name}:{tag}",
        "tag": tag,
        "digest": digest,
        "last_published": published,
        "pulls": pulls,
        "description": first_line(description),
        "repo": repo,
        "reason": reason,
    }


def hub_repos(namespace: str) -> list[dict]:
    """Every public repository of a Docker Hub namespace."""
    url, found = f"https://hub.docker.com/v2/namespaces/{quote(namespace)}/repositories?page_size=100", []
    while url:
        page = fetch_json(url)
        found += page["results"]
        url = page["next"]
    return found


def hub_image(namespace: str, repo: dict, find_repo) -> dict | None:
    """What Docker Hub says about one image, or None if it has no tag."""
    name = repo["name"]
    tags = f"https://hub.docker.com/v2/repositories/{quote(namespace)}/{quote(name)}/tags"
    tag = fetch_json(f"{tags}/latest")
    if tag is None:  # the API lists the newest tag first
        newest = (fetch_json(f"{tags}?page_size=1") or {}).get("results")
        tag = newest[0] if newest else None
    if tag is None:
        return None
    builds = tag.get("images") or []  # a single-platform image has no digest of its own: it is its one build's
    digest = tag.get("digest") or (builds[0]["digest"] if len(builds) == 1 else None)
    published = (tag.get("tag_last_pushed") or tag["last_updated"])[:10]
    return describe(
        "docker.io", namespace, name, tag["name"], digest, published, repo["pull_count"], repo["description"], find_repo
    )


def quay_repos(namespace: str) -> list[dict]:
    """Every public repository of a Quay namespace."""
    url, found, token = f"https://quay.io/api/v1/repository?namespace={quote(namespace)}&public=true", [], None
    while True:
        page = fetch_json(url + (f"&next_page={quote(token)}" if token else ""))
        found += page["repositories"]
        token = page.get("next_page")
        if not token:
            return found


def quay_image(namespace: str, repo: dict, find_repo) -> dict | None:
    """What Quay says about one image, or None if it has no tag."""
    name = repo["name"]
    tags = f"https://quay.io/api/v1/repository/{quote(namespace)}/{quote(name)}/tag/?limit=1&onlyActiveTags=true"
    # `limit=1` of the unfiltered list is the newest tag
    for url in (f"{tags}&specificTag=latest", tags):
        found = (fetch_json(url) or {}).get("tags")
        if found:
            break
    else:
        return None
    tag = found[0]
    published = datetime.datetime.fromtimestamp(tag["start_ts"], datetime.UTC).date().isoformat()
    return describe(
        "quay.io",
        namespace,
        name,
        tag["name"],
        tag.get("manifest_digest"),
        published,
        None,
        repo.get("description"),
        find_repo,
    )


def export(images: list[dict]) -> str:
    """The text of output/images.txt: one reference per line, nothing else, so `xargs` can read it."""
    return "".join(image["reference"] + "\n" for image in images)


def main():
    inventory = load_json(OUTPUT / "repos.json")
    scan = load_json(OUTPUT / "scan.json")
    unknown = {ns for namespaces in NAMESPACES.values() for ns in namespaces} - set(inventory["orgs"])
    if unknown:
        raise SystemExit(
            f"{sorted(unknown)} in NAMESPACES are not GitHub organizations of the inventory (ORGS, step 1)"
        )

    # Forks are skipped, as in step 3: a fork has the chartpress file of its original, but does not build the image.
    repo_names = {repo["full_name"].lower(): repo["full_name"] for repo in inventory["repos"] if not repo["is_fork"]}
    builders = {}
    for repo, found in scan.items():
        for ref in found["images"]:
            builders.setdefault(image_path(ref), set()).add(repo.lower())

    def find_repo(namespace, name, description):
        return source_repo(namespace, name, description, repo_names, builders)

    jobs = [(hub_image, namespace, repo) for namespace in NAMESPACES["docker.io"] for repo in hub_repos(namespace)] + [
        (quay_image, namespace, repo) for namespace in NAMESPACES["quay.io"] for repo in quay_repos(namespace)
    ]
    with ThreadPoolExecutor(4) as pool:
        found = pool.map(lambda job: job[0](job[1], job[2], find_repo), jobs)
        images = sorted(filter(None, found), key=lambda i: (i["registry"], i["namespace"], i["name"]))

    save_json(OUTPUT / "images.json", {"fetched_on": str(datetime.date.today()), "images": images})
    (OUTPUT / "images.txt").write_text(export(images), encoding="utf-8")
    print(f"{len(images)} images from {len(jobs)} repositories in {sum(map(len, NAMESPACES.values()))} namespaces")


if __name__ == "__main__":
    main()
