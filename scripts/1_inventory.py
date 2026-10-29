"""Step 1: list the public repositories of the GitHub organizations in ORGS.

Archived and empty repos are left out: archived ones are read-only, run no CI and cut no releases,
and empty ones have no code, so there is nothing in them to secure.

Usage: python scripts/1_inventory.py    Needs: the GitHub CLI (`gh auth login`).
Output: output/repos.json
"""

import datetime
import json
import subprocess

from common import OUTPUT, save_json

# The GitHub organizations of Project Jupyter, written by hand.
ORGS = [
    "binder-examples",
    "binderhub-ci-repos",
    "ipython",
    "jupyter",
    "jupyter-book",
    "jupyter-governance",
    "jupyter-incubator",
    "jupyter-resources",
    "jupyter-server",
    "jupyter-standard",
    "jupyter-standards",
    "jupyter-widgets",
    "jupyter-xeus",
    "jupytercon",
    "jupyterhealth",
    "jupyterhub",
    "jupyterlab",
    "jupyterlite",
    "voila-dashboards",
    "voila-gallery",
]


def public_repos(org: str) -> list[dict]:
    command = [
        "gh",
        "repo",
        "list",
        org,
        "--visibility",
        "public",
        "--no-archived",
        "--limit",
        "1000",
        "--json",
        "nameWithOwner,description,isFork,isEmpty",
    ]
    listing = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)
    repos = []
    for item in listing:
        if item["isEmpty"]:
            continue
        full_name = item["nameWithOwner"]
        repos.append(
            {
                "full_name": full_name,
                "org": org,
                "name": full_name.split("/")[1],
                "description": item["description"] or None,
                "is_fork": item["isFork"],
            }
        )
    return repos


def main():
    repos = [repo for org in ORGS for repo in public_repos(org)]
    repos.sort(key=lambda repo: repo["full_name"].lower())
    save_json(OUTPUT / "repos.json", {"fetched_on": str(datetime.date.today()), "orgs": ORGS, "repos": repos})
    print(f"{len(repos)} public, non-archived repos in {len(ORGS)} orgs")


if __name__ == "__main__":
    main()
