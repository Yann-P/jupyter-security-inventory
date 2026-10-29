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
| 4. Images | Lists the container images published on Docker Hub and Quay and matches them to repositories, with the tag people pull, its digest, Docker Hub's pull count and the date it was pushed. Also writes `output/images.txt` for image scanners | Docker Hub, Quay |
| 5. Labels | Decides each repository's kind, the live service it deploys and whether it's a security boundary, and why | LLM |
| 6. Merge | Puts it all together and works out which repositories run each other's code | |
| 7. Table | Writes `output/repos.csv` | |

[architecture.md](https://github.com/Yann-P/jupyter-security-inventory/blob/main/architecture.md) explains how the pieces fit together.

## The columns

- **kind**: package, application, tooling, deployment, documentation, example or other.
- **downloads/month** and **dependents**: for the repository's most downloaded package.
- **images**: how many container images come from the repository.
- **used in CI**: how many other Jupyter repositories run its actions or build tools without pinning them
  to a commit.
- **live service**: the site or service it deploys, like mybinder.org.
- **security boundary**: whether its bugs can be exploited over the network, because it handles logins,
  proxies traffic, runs multi-user servers or runs code and content from the network, and why.

## Caveats

- **Repository type, and security boundary come from a language model**
- Download counts include CI.
- Images: ghcr.io is not covered (it lists nothing without authentication), Quay publishes no pull counts, Docker
  Hub's are all-time counts, and only the tag people get by default is recorded. The Docker Hub and Quay namespaces to
  look at are listed by hand in `scripts/4_images.py`. An image's repository is the one whose chartpress file builds
  it, else the one its description links to, else the one named like it; many older images have none.
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

## Scanning the images

`output/images.txt` has one image reference per line and nothing else, so any image scanner can read it and
nothing here depends on one. Scanners pull the images themselves, so run them from your own machine or CI, on
the file in a checkout or downloaded from
`https://raw.githubusercontent.com/Yann-P/jupyter-security-inventory/main/output/images.txt`. Some tools worth
trying:

- [Trivy](https://trivy.dev): known vulnerabilities in the operating system and in Python, npm and other packages,
  plus secrets and misconfigurations. A good first scanner.
- [Grype](https://github.com/anchore/grype), with [Syft](https://github.com/anchore/syft) to list what an image
  contains (an SBOM): known vulnerabilities again, from another database, so the two disagree usefully.
- [Dockle](https://github.com/goodwithtech/dockle): not vulnerabilities but how the image is built, like running as
  root or leaving secrets and credentials in it.
- [Docker Scout](https://docs.docker.com/scout/) (`docker scout cves`): the same idea, built into Docker.

```bash
# Trivy: a JSON report per image, in reports/
mkdir -p reports
while read -r image; do
  trivy image --severity HIGH,CRITICAL --format json --output "reports/$(echo "$image" | tr '/:' '__').json" "$image"
done < output/images.txt

# Grype: a table per image
xargs -n1 grype < output/images.txt
```

`output/images.json` has the digest of each image, to find out which images are the same on both registries, and
the repositories each image points to, to find who to report to.

## Daily updates

A GitHub Actions workflow (`update.yml`) reruns the whole pipeline every morning, commits what changed in
`output/` and republishes the site. It needs a `DEEPSEEK_API_KEY` repository secret.

Step 5 only labels repositories it hasn't labeled yet with the current model, so a daily run costs almost
nothing. To relabel everything, switch to another model or delete `output/classification.json`.

## Contributing

Change the scripts, never `output/` by hand. Rerun the pipeline from the step you changed, run `pytest`,
and commit the new outputs with your change. CI runs the tests and checks that the outputs match the code.

## License

BSD 3-Clause.
