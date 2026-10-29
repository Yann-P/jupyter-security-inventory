# Jupyter Security Inventory

Project Jupyter has over 400 public repositories across 20 GitHub organizations. This project collects, for each repository, some data like how many people install it, how many other Jupyter repositories run its code in CI, whether it runs a live service, and whether it's a security boundary.

## Eventual goals

- Expose a "todo list" of bite-sized security improvements from which contributors can pick from.
- Be a tool to prioritize where security time is spent first using metrics
- And eventually aggregate more data (trusted publishing, zizmor, check SECURITY.mds) in an effort to centralize what we do manually in https://github.com/jupyter/security/issues.

## Structure

- In `output/`: the raw result of each step below, one readable JSON file per step. Do not write here.
- In `site/data/`: the files that join those results, one record per repository and per package, which the page loads. Written by step 5. Do not write here.
- In `site/`: a static page that loads `site/data/` and draws it in the browser. Plain HTML and JavaScript modules, no build step, no npm. Its one dependency, Tabulator, is copied into `site/vendor/`.

## How it works

Five scripts run in order (they depend on each other):

| Step | What it does | Data from |
|---|---|---|
| 1. Inventory | Lists the public, non-archived repositories of each organization | GitHub |
| 2. Scan | Clones each repository and reads its workflows, actions, package manifests and README | GitHub |
| 3. Packages | Matches PyPI and npm packages to repositories, with downloads and dependents | PyPI, npm, pypistats.org, deps.dev |
| 4. Labels | Decides each repository's kind, the live service it deploys and whether it's a security boundary, and why | LLM |
| 5. Join | Puts it all together in `site/data/`, and works out which repositories run each other's code | |

## The columns

- **kind**: package, application, tooling, deployment, documentation, example or other.
- **downloads/month** and **dependents**: for the repository's most downloaded package.
- **used in CI**: how many other Jupyter repositories run its actions or build tools without pinning them
  to a commit.
- **live service**: the site or service it deploys, like mybinder.org.
- **security boundary**: whether its bugs can be exploited over the network, because it handles logins,
  proxies traffic, runs multi-user servers or runs code and content from the network, and why.

The data has more fields than these (workflows, files, dates, who uses whom). The docstring of `scripts/5_build_dataset.py` says how they are made and `tests/test_site_data.py` lists them all, with their types.

## Caveats

- **Repository type, and security boundary come from a language model**
- Download counts include CI.
- "Used in CI" only sees the repositories listed here.

## Running it

You need Python >= 3.14, the GitHub CLI (logged in), and a DeepSeek API key for step 4 (or an OpenAI key,
with `--model <an OpenAI model>`).

```bash
pip install . --group dev
python scripts/1_inventory.py
python scripts/2_scan_repos.py --clone-dir ~/clones
python scripts/3_packages.py
python scripts/4_classify.py --clone-dir ~/clones
python scripts/5_build_dataset.py
python3 -m http.server -d site
```

Then open http://localhost:8000. The page has to be served over HTTP, because browsers will not let a page opened
as a file read the JSON next to it, but any static file server will do. The committed `site/data/` is enough to
browse the page without running the scripts.

## Adding a view

Add one object to the list in `site/views.js`: an id, a title, which records to list, which columns to show. The
comment at the top of that file explains each key and has a worked example. Nothing else changes.

## Adding an inventory

1. A fetch script, `scripts/<n>_<name>.py`, that writes `output/<name>.json`.
2. A join in step 5 that writes `site/data/<name>.json`: one record per entity, each with an `id`, and ids wherever
   it refers to another record.
3. The invariants of the new file in `tests/test_site_data.py`: unique ids, references that resolve, the fields
   and their types.
4. A view that lists it in `site/views.js` (and, if the page does not know the file yet, the line in `site/app.js`
   that loads the data files).

## Daily updates

A GitHub Actions workflow (`update.yml`) reruns the whole pipeline every morning and commits what changed in
`output/` and `site/data/`. It needs a `DEEPSEEK_API_KEY` repository secret. The site is plain static files, so
hosting `site/` is up to you.

Step 4 only labels repositories it hasn't labeled yet with the current model, so a daily run costs almost
nothing. To relabel everything, switch to another model or delete `output/classification.json`.

## Contributing

Change the scripts or the code of the page, never `output/` or `site/data/` by hand. Rerun the pipeline from the
step you changed, run `pytest`, and commit the new data with your change. CI runs the tests, checks the syntax
of the JavaScript and checks that `site/data/` matches the code.

## License

BSD 3-Clause.
