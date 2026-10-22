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

Six scripts run in order (they depend on each other):

| Step | What it does | Data from |
|---|---|---|
| 1. Inventory | Lists the public, non-archived repositories of each organization | GitHub |
| 2. Scan | Clones each repository and reads its workflows, actions, package manifests and README | GitHub |
| 3. Packages | Matches PyPI and npm packages to repositories, with downloads and dependents | PyPI, npm, pypistats.org, deps.dev |
| 4. Labels | Decides each repository's kind, the live service it deploys and whether it's a security boundary, and why | LLM |
| 5. Merge | Puts it all together and works out which repositories run each other's code | |
| 6. Table | Writes `output/repos.csv` | |

## The columns

- **kind**: package, application, tooling, deployment, documentation, example or other.
- **downloads/month** and **dependents**: for the repository's most downloaded package.
- **used in CI**: how many other Jupyter repositories run its actions or build tools without pinning them
  to a commit.
- **live service**: the site or service it deploys, like mybinder.org.
- **security boundary**: whether its bugs can be exploited over the network, because it handles logins,
  proxies traffic, runs multi-user servers or runs code and content from the network, and why.

## Caveats

- **Repository type, and security boundary come from a language model**
- Download counts include CI.
- "Used in CI" only sees the repositories listed here.

## Running it

You need Python >= 3.14, the GitHub CLI (logged in), and a DeepSeek API key for step 4 (or an OpenAI key,
with `--model <an OpenAI model>`).

```bash
pip install . --group dev --group docs
python scripts/1_inventory.py
python scripts/2_scan_repos.py --clone-dir ~/clones
python scripts/3_packages.py
python scripts/4_classify.py --clone-dir ~/clones
python scripts/5_build_dataset.py
python scripts/6_table.py
```

## Daily updates

A GitHub Actions workflow (`update.yml`) reruns the whole pipeline every morning, commits what changed in
`output/` and republishes the site. It needs a `DEEPSEEK_API_KEY` repository secret.

Step 4 only labels repositories it hasn't labeled yet with the current model, so a daily run costs almost
nothing. To relabel everything, switch to another model or delete `output/classification.json`.

## Contributing

Change the scripts, never `output/` by hand. Rerun the pipeline from the step you changed, run `pytest`,
and commit the new outputs with your change. CI runs the tests and checks that the outputs match the code.

## License

BSD 3-Clause.
