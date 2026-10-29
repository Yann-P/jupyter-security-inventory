"""Step 7: write output/repos.csv, the table shown on the site. One row per repo, one column per metric.

    python scripts/7_table.py

The columns:
  package            its most downloaded package
  downloads/month    monthly downloads of that package
  dependents         how many packages depend on it
  image              its most pulled container image
  all-time pulls     Docker Hub pulls of that image (Quay has none)
  used in CI         how many other repos run its GitHub Actions or build tools in their CI or releases.
                     Repos that pin its actions to a commit SHA are not counted.
  live service       the website or service it deploys
  security boundary  why it is one, if it is: it handles logins, proxies traffic, runs multi-user servers
                     or runs code and content from the network
"""

import csv

from common import OUTPUT, load_json

TABLE = OUTPUT / "repos.csv"


def row(repo: dict) -> dict:
    labels, used_by = repo["classification"], repo["used_by"]
    has_package = repo["top_package"] is not None
    return {
        "repo": repo["full_name"],
        "kind": labels["kind"],
        "package": repo["top_package"] or "",
        "downloads/month": repo["max_downloads_last_month"] if has_package else "",
        "dependents": repo["top_package_dependents"] if has_package else "",
        "image": repo["top_image"] or "",
        "all-time pulls": "" if repo["top_image_pulls"] is None else repo["top_image_pulls"],
        "used in CI": len(set(used_by["ci"] + used_by["build"])) or "",
        "live service": labels["deploys_live_service"] or "",
        "security boundary": labels["security_boundary"] or "",
    }


def main():
    repos = load_json(OUTPUT / "jupyter_repos.json")["repos"]
    rows = sorted((row(repo) for repo in repos), key=lambda r: r["repo"])
    with open(TABLE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} repos to output/repos.csv")


if __name__ == "__main__":
    main()
