# Jupyter Security Inventory

Project Jupyter has over 400 public repositories across 20 GitHub organizations. This project collects, for each repository, some data like how many people install it, how many other Jupyter repositories run its code in CI, whether it runs a live service, and whether it's a security boundary.

## Eventual goals

- Expose a "todo list" of bite-sized security improvements from which contributors can pick from.
- Be a tool to prioritize where security time is spent first using metrics
- And eventually aggregate more data (trusted publishing, zizmor, check SECURITY.mds) in an effort to centralize what we do manually in https://github.com/jupyter/security/issues.

## Structure

- In `output/`: the results of the scripts described below. Do not write here.
- In `docs/`: a sphinx website that makes the results browsable.

## How it works

Seven scripts run in order (they depend on each other):

| Step | What it does | Data from |
|---|---|---|
| 1. Inventory | Lists the public, non-archived repositories of each organization | GitHub |
| 2. Scan | Clones each repository and reads its workflows, actions, package manifests, chartpress files and README | GitHub |
| 3. Packages | Matches PyPI and npm packages to repositories, with downloads, dependents and the date of the last release | PyPI, npm, pypistats.org, deps.dev |
| 4. Images | Lists the images published on Docker Hub and Quay and matches them to repositories. Also writes `output/images.txt`, one image per line | Docker Hub, Quay |
| 5. Labels | Decides each repository's kind, the live service it deploys and whether it's a security boundary, and why | LLM |
| 6. Merge | Puts it all together and works out which repositories run each other's code | |
| 7. Table | Writes `output/repos.csv` | |

[architecture.md](https://github.com/Yann-P/jupyter-security-inventory/blob/main/architecture.md) explains how the pieces fit together.

## The columns

- **kind**: package, application, tooling, deployment, documentation, example or other.
- **downloads/month** and **dependents**: for the repository's most downloaded package.
- **image** and **all-time pulls**: for the repository's most pulled container image.
- **used in CI**: how many other Jupyter repositories run its actions or build tools without pinning them
  to a commit.
- **live service**: the site or service it deploys, like mybinder.org.
- **security boundary**: whether its bugs can be exploited over the network, because it handles logins,
  proxies traffic, runs multi-user servers or runs code and content from the network, and why.

## Caveats

- **Repository type, and security boundary come from a language model**
- Download counts include CI.
- A package is found only through a repository of this inventory.
- Images: ghcr.io is not covered, Quay has no pull counts, and one tag is recorded per image: `latest`, or the newest.
  The namespaces are listed by hand in `scripts/4_images.py`. Many older images match no repository.
- "Used in CI" only sees the repositories listed here.

## Running it

You need Python >= 3.14, the GitHub CLI (logged in), and a DeepSeek API key for step 5 (or an OpenAI key,
with `--model <an OpenAI model>`).

```bash
pip install . --group dev --group docs
python scripts/1_inventory.py
python scripts/2_scan_repos.py --clone-dir ~/clones
python scripts/3_packages.py
python scripts/4_images.py
python scripts/5_classify.py --clone-dir ~/clones
python scripts/6_build_dataset.py
python scripts/7_table.py
```

## Daily updates

A GitHub Actions workflow (`update.yml`) reruns the whole pipeline every morning, commits what changed in
`output/` and republishes the site. It needs a `DEEPSEEK_API_KEY` repository secret.

Step 5 only labels repositories it hasn't labeled yet with the current model, so a daily run costs almost
nothing. To relabel everything, switch to another model or delete `output/classification.json`.

## Contributing

Change the scripts, never `output/` by hand. Rerun the pipeline from the step you changed, run `pytest`,
and commit the new outputs with your change. CI runs the tests and checks that `jupyter_repos.json` and `repos.csv` are up to date.

The daily update and the site build install `requirements.txt` and `requirements-docs.txt`, which pin every
dependency, including indirect ones, to an exact version and hash. After changing the dependencies in
`pyproject.toml`, regenerate them with the command on the second line of each file.

## License

BSD 3-Clause.
