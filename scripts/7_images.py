"""Step 7: the container images that Jupyter publishes on Docker Hub and Quay.

For each image: the tag people pull (`latest`, or the newest tag when there is none), its digest, when it was
pushed, how often Docker Hub says it was pulled, and `repos`: the inventory repositories its description links to,
or that are named like it. Images with no tag are left out: there is nothing to pull.

Also writes output/images.txt, one pullable reference per line, so any image scanner can read the list without
knowing this project's formats:  xargs -n1 trivy image < output/images.txt

Limits: ghcr.io cannot list a namespace without authentication, so it is not covered. Quay publishes no pull
counts. Only one tag per image is recorded; the others are older builds of the same image.

Usage: python scripts/7_images.py    Needs: output/repos.json (step 1)
Output: output/images.json, output/images.txt
"""

import datetime
from concurrent.futures import ThreadPoolExecutor

from common import OUTPUT, fetch_json, github_repos_in, load_json, quote, save_json

# The registry namespaces of Project Jupyter: the only input maintained by hand, like ORGS in step 1.
# A namespace is not always the GitHub organization's: on Docker Hub, `jupytercon` holds throwaway images built
# for conference tutorials, and `binder` and `voila` hold one image each that nothing links to Jupyter.
# So every namespace here was checked by hand.
NAMESPACES = {
    "docker.io": ["ipython", "jupyter", "jupyterhub"],
    "quay.io": ["jupyter", "jupyterhealth", "jupyterhub"],
}


def first_line(text: str | None) -> str | None:
    """The first line of a description, without Markdown heading marks: Quay descriptions are whole READMEs."""
    for line in (text or "").splitlines():
        if line.strip("# \t"):
            return line.strip("# \t")
    return None


def linked_repos(namespace: str, name: str, description: str | None, repo_names: dict) -> list[str]:
    """The inventory repos the description links to, else the repo named like the image in the namespace's org.

    `repo_names` maps lower-case 'org/repo' to the real name, because GitHub names ignore case.
    """
    linked = github_repos_in(description) & repo_names.keys()
    if not linked and f"{namespace}/{name}".lower() in repo_names:
        linked = {f"{namespace}/{name}".lower()}
    return sorted(repo_names[name] for name in linked)


def hub_repos(namespace: str) -> list[dict]:
    """Every public repository of a Docker Hub namespace."""
    url, found = f"https://hub.docker.com/v2/namespaces/{quote(namespace)}/repositories?page_size=100", []
    while url:
        page = fetch_json(url)
        found += page["results"]
        url = page["next"]
    return found


def hub_image(namespace: str, repo: dict, repo_names: dict) -> dict | None:
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
    return {
        "registry": "docker.io",
        "namespace": namespace,
        "name": name,
        "reference": f"docker.io/{namespace}/{name}:{tag['name']}",
        "tag": tag["name"],
        "digest": digest,
        "last_pushed": (tag.get("tag_last_pushed") or tag["last_updated"])[:10],
        "pulls": repo["pull_count"],
        "description": first_line(repo["description"]),
        "repos": linked_repos(namespace, name, repo["description"], repo_names),
    }


def quay_repos(namespace: str) -> list[dict]:
    """Every public repository of a Quay namespace."""
    url, found, token = f"https://quay.io/api/v1/repository?namespace={quote(namespace)}&public=true", [], None
    while True:
        page = fetch_json(url + (f"&next_page={quote(token)}" if token else ""))
        found += page["repositories"]
        token = page.get("next_page")
        if not token:
            return found


def quay_image(namespace: str, repo: dict, repo_names: dict) -> dict | None:
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
    pushed = datetime.datetime.fromtimestamp(tag["start_ts"], datetime.UTC).date().isoformat()
    return {
        "registry": "quay.io",
        "namespace": namespace,
        "name": name,
        "reference": f"quay.io/{namespace}/{name}:{tag['name']}",
        "tag": tag["name"],
        "digest": tag.get("manifest_digest"),
        "last_pushed": pushed,
        "pulls": None,
        "description": first_line(repo.get("description")),
        "repos": linked_repos(namespace, name, repo.get("description"), repo_names),
    }


def export(images: list[dict]) -> str:
    """The text of output/images.txt: one reference per line, nothing else, so `xargs` can read it."""
    return "".join(image["reference"] + "\n" for image in images)


def main():
    inventory = load_json(OUTPUT / "repos.json")
    repo_names = {repo["full_name"].lower(): repo["full_name"] for repo in inventory["repos"]}

    jobs = [(hub_image, namespace, repo) for namespace in NAMESPACES["docker.io"] for repo in hub_repos(namespace)] + [
        (quay_image, namespace, repo) for namespace in NAMESPACES["quay.io"] for repo in quay_repos(namespace)
    ]
    with ThreadPoolExecutor(4) as pool:
        found = pool.map(lambda job: job[0](job[1], job[2], repo_names), jobs)
        images = sorted(filter(None, found), key=lambda i: (i["registry"], i["namespace"], i["name"]))

    save_json(OUTPUT / "images.json", {"fetched_on": str(datetime.date.today()), "images": images})
    (OUTPUT / "images.txt").write_text(export(images), encoding="utf-8")
    print(f"{len(images)} images from {len(jobs)} repositories in {sum(map(len, NAMESPACES.values()))} namespaces")


if __name__ == "__main__":
    main()
