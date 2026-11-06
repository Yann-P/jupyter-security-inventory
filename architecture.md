# Architecture

Two parts: a **pipeline** of eight Python scripts that writes data files, and a **site** that reads them.

```
GitHub, PyPI, npm, pypistats.org, deps.dev, Docker Hub, Quay, an LLM
        │
        ▼
scripts/1..8  ──►  output/*.json, *.csv, *.txt  ──►  docs/insights.py  ──►  Sphinx site
 (pipeline)        (committed to git)                (writes the pages)      (GitHub Pages)
```

## Rules

- Data flows one way. A script reads only the outputs of earlier steps.
- `output/` is written by the scripts only. Never edit it by hand (see Contributing in the README).
- The outputs are committed, so the site builds without network access and every change shows up in git.
- Inputs written by hand: `ORGS` (step 1), `NAMESPACES` (step 4), the prompt and model (step 5), the topics (step 8).
- Deciding and showing are separate. `scripts/topics/` decides what a repo is missing; the site only shows `topics.json`.

## The pipeline

| Step | Script | Reads | Writes |
|---|---|---|---|
| 1 | `1_inventory.py` | `ORGS`, GitHub | `repos.json` |
| 2 | `2_scan_repos.py` | `repos.json`, GitHub clones | `scan.json` |
| 3 | `3_packages.py` | `repos.json`, `scan.json`, PyPI, npm, pypistats, deps.dev | `packages.json` |
| 4 | `4_images.py` | `NAMESPACES`, `repos.json`, `scan.json`, Docker Hub, Quay | `images.json`, `images.txt` |
| 5 | `5_classify.py` | `repos.json`, `scan.json`, `packages.json`, clones, LLM | `classification.json` |
| 6 | `6_build_dataset.py` | steps 1 to 5 | `jupyter_repos.json` |
| 7 | `7_table.py` | `jupyter_repos.json` | `repos.csv` |
| 8 | `8_topics.py` | `scan.json`, `jupyter_repos.json` | `topics.json`, `topics_history.json` |

`common.py` has what the scripts share: reading and writing JSON, and `fetch_json`, which caches answers for
24 hours in `.cache/http/` and retries on rate limits (HTTP 429) and server errors.

Step 2 keeps, for each repo: file counts by type, the packages its manifests declare, a summary of its workflows
(triggers, secrets, what they publish), the actions it uses, the images its chartpress files build, the build
requirements of its `pyproject.toml`, the start of its README, its SECURITY.md and the emails in it, and which of a few words (zizmor, pre-commit) its CI files and
pre-commit config mention. A clone is shallow and holds only those files.
Symbolic links are never followed.

## Matching packages and images to repos

Each match carries a `reason`. Forks never match: a fork has the files of its original, but does not publish.

- **Package → repo** (step 3): a manifest of the repo declares the package, or the package is named like the repo;
  and PyPI or npm confirms it (it links to the repo, or it has a Jupyter owner). If several repos qualify, the one
  the registry links to wins.
- **Image → repo** (step 4), first match wins: the repo's chartpress file builds the image; the registry description
  links to the repo; the repo is named like the image. Many older images match none.
- **Image → organization**: its registry namespace. Each namespace in `NAMESPACES` must be an organization with
  repos in the inventory; step 4 stops if not.

## The data files

All in `output/`. Repos are named `org/repo`.

| File | Shape |
|---|---|
| `repos.json` | `fetched_on`, `orgs`, and `repos`: full_name, org, name, description, is_fork. |
| `scan.json` | `{repo: facts from step 2}`. |
| `packages.json` | `accepted`: system (PYPI or NPM), name, repo, reason, downloads_last_month, dependents, last_published, and for the latest release (the default version): latest_published, and `attested` and `requires_python` (PyPI) or `trusted_publishing` (npm). `rejected`: candidates that were not confirmed. |
| `images.json` | `images`: registry, namespace, name, tag, last_published, pulls (all time), reference, repo, reason. |
| `images.txt` | One image reference per line. |
| `classification.json` | `{repo: kind, security_boundary, deploys_live_service, rationale, model}`. Written by an LLM. |
| `jupyter_repos.json` | The repo from step 1, plus its packages, images, content, `used_by` and classification. |
| `repos.csv` | The columns of the repo tables. |
| `topics.json` | `topics`: id, title, question, how it is detected, what each status means. `results`: a row per topic and repo with its status, reason, how it is done (`via`) and the files that show it (`evidence`). |
| `topics_history.json` | `{day: {topic: {status: number of repos}}}`, for each day the inventory was fetched. |

`used_by` (step 6) lists the other repos that run a repo's code. `ci`: they use its GitHub Actions in a workflow.
`ci_pinned`: the same, pinned to a commit, so a compromise of the action does not reach them by itself. `build`:
they use its packages in their build requirements. "Used in CI" counts `ci` and `build`.

## Security topics

A topic answers one question about every repo, like "does it run zizmor?". It is a module in `scripts/topics/` with a
`check` function. `check` reads a repo's record in `jupyter_repos.json`, with the day it was fetched, and all of `scan.json`, and returns a status (`done`, `partial`, `missing` or
`n/a`), a short reason, how the repo does it, and the files that show it. Step 8 writes a row per repo and topic, so a
new topic adds rows, not columns, and counts the statuses once a day for the "over time" table.

The zizmor topic knows three ways to run it: its GitHub Action, a command in a workflow (`uvx zizmor`) and a pre-commit
hook. The first two are `done`. A hook is `done` if CI runs pre-commit: a workflow runs it, or the config has a `ci:`
section for pre-commit.ci (we can't see whether it is installed). Otherwise it is `partial`. A repo with no workflows is
`n/a`. Zizmor from super-linter is not recognized.

The SECURITY.md topic looks where GitHub does: the repo's `.github` folder, root and `docs` folder, then the same in
the org's `.github` repo. Only repos that ship a package or an image need one. When the repo and its org both have
one, the repo's file is likely a copy (`done`) if it lists the same emails, and `partial` if not, since reports may
go to an old address.

The PyPI attestations and npm trusted publishing topics read what step 3 asked the registries about each package's
latest release, however old it is.

The supported Python topic finds the oldest Python that the Requires-Python of each package's latest release allows,
and compares the day CPython stops its security fixes with the day the inventory was fetched, not today, so that CI
gets the same answers. Those days are written in the topic, from peps.python.org.

## The site

`docs/conf.py` calls `insights.build()` every time Sphinx starts. It reads `output/`, then writes the CSV tables and
the body of the home page to `docs/_generated/` and a page per organization and repo to `docs/orgs/`, and a page per
topic to `docs/topics/`. These folders are generated and not committed. The other pages are written by hand and include those tables.

| Page | Content | Source |
|---|---|---|
| All organizations (`index.md`) | The sections of an organization page, for all of them: security topics, repos, packages (PyPI, npm) and images. Its body is `_generated/home.md` | `jupyter_repos.json`, `images.json`, `repos.csv` |
| Organizations (`orgs.md`) | One page per organization that has a repo: its topics, repos, packages (PyPI, npm) and images, and one page per repo below it. Empty tables and sections are left out | `jupyter_repos.json`, `images.json` |
| Security topics (`topics.md`) | The home page's table of topics, and a page per topic: a table by organization, the repos, most downloaded first, and the days the numbers changed | `topics.json`, `topics_history.json` |
| Published packages (`packages.md`) | A summary table, then a page with one table for PyPI and one for npm (the home page's tables) | `jupyter_repos.json` |
| Container images (`images.md`) | One table of images (the home page's table) | `images.json` |
| About (`about.md`) | The README | `README.md` |

How the pages link to each other:

- The repo tables (home and organization pages) link each repo to its page. The `image` column shows its most
  pulled image, as `package` does for packages.
- A repo page lists its packages and its images, with links to the registries, and what each topic found.
- The package and image tables link each row to the registry, and to its organization page and its repo page when
  there is one. On an organization page they are the same tables without the organization column. An image belongs
  to the organization of its namespace.
- Package and image tables share the columns organization, repository and last published. Usage is downloads per
  month for packages and all-time pulls for images. Only the repo tables are tinted by kind.

Every table has a "Download CSV" link to its rows as plain text, without links or thousands separators, in
`docs/_generated/downloads/<stem>.csv`. A stem is `<organization>-<table>`, `all-<table>` for the tables of the home
page, or `orgs` and `packages`; the hand-written pages link to theirs by hand.

The class `sphinx-datatable` makes a table sortable and searchable (DataTables). `docs/_static/tables.js` hides
everything but the sorting on a table of 10 rows or fewer, and adds a filter on the column named "organization" to
the tables with the class `filter-by-org`.

Text that comes from repos or the LLM (descriptions, labels, rationales) goes through `plain()` in `insights.py`,
so it is shown as text and never becomes HTML, a link or a substitution.

## Automation

| Workflow | When | What |
|---|---|---|
| `ci.yml` | each push to `main` and each pull request | Formatting (pre-commit, ruff), the tests, and a check that the outputs of steps 6 to 8 match the code. Steps 1 to 5 need the network or an LLM, so they are not rerun. |
| `docs.yml` | each push to `main` and each pull request | Builds the site with warnings as errors and pushes it to the `gh-pages` branch, which GitHub Pages serves: `main` at the root, and each pull request from this repo at `pr-preview/pr-<number>/` until it closes, with a link in a comment. |
| `update.yml` | every day | Runs steps 1 to 8, commits `output/`, then calls `docs.yml`. |

Actions are pinned to commit SHAs.

## Adding things

- **A registry namespace:** add it to `NAMESPACES` in step 4, after checking that it belongs to Jupyter. A Docker Hub
  namespace named like a Jupyter organization can belong to someone else. It must also be an organization of `ORGS`.
- **A column in the repo tables:** add it in `7_table.py` and in `repo_rows` of `insights.py`.
- **A security topic:** write a module in `scripts/topics/` like `zizmor.py` and add it to `TOPICS` in step 8. If it needs a
  fact step 2 does not keep, such as a word to find in workflows, add it to `MENTIONS` there and rerun step 2. The site
  needs no change.
- **Another kind of published thing:** a new step before step 6 that writes its own file with a `repo` and a
  `reason`; read it in step 6; add a table like the package and image tables.
