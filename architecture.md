# Architecture

Two parts: a **pipeline** of seven Python scripts that writes data files, and a **site** that reads them.

```
GitHub, PyPI, npm, pypistats.org, deps.dev, Docker Hub, Quay, an LLM
        │
        ▼
scripts/1..7  ──►  output/*.json, *.csv, *.txt  ──►  docs/insights.py  ──►  Sphinx site
 (pipeline)        (committed to git)                (writes the pages)      (GitHub Pages)
```

## Rules

- Data flows one way. A script reads only the outputs of earlier steps.
- `output/` is written by the scripts only. Never edit it by hand (see Contributing in the README).
- The outputs are committed, so the site builds without network access and every change shows up in git.
- Inputs written by hand: `ORGS` (step 1), `NAMESPACES` (step 4), the prompt and model (step 5).

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

`common.py` has what the scripts share: reading and writing JSON, and `fetch_json`, which caches answers for
24 hours in `.cache/http/` and retries on rate limits (HTTP 429) and server errors.

Step 2 keeps, for each repo: file counts by type, the packages its manifests declare, a summary of its workflows
(triggers, secrets, what they publish), the actions it uses, the images its chartpress files build, the build
requirements of its `pyproject.toml`, and the start of its README. A clone is shallow and holds only those files.
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
| `packages.json` | `accepted`: system (PYPI or NPM), name, repo, reason, downloads_last_month, dependents, last_published. `rejected`: candidates that were not confirmed. |
| `images.json` | `images`: registry, namespace, name, tag, last_published, pulls (all time), reference, repo, reason. |
| `images.txt` | One image reference per line. |
| `classification.json` | `{repo: kind, security_boundary, deploys_live_service, rationale, model}`. Written by an LLM. |
| `jupyter_repos.json` | The repo from step 1, plus its packages, images, content, `used_by` and classification. |
| `repos.csv` | The columns of the repo tables. |

`used_by` (step 6) lists the other repos that run a repo's code. `ci`: they use its GitHub Actions in a workflow.
`ci_pinned`: the same, pinned to a commit, so a compromise of the action does not reach them by itself. `build`:
they use its packages in their build requirements. "Used in CI" counts `ci` and `build`.

## The site

`docs/conf.py` calls `insights.build()` every time Sphinx starts. It reads `output/`, then writes the CSV tables to
`docs/_generated/` and a page per organization and repo to `docs/orgs/`. Both folders are generated and not
committed. The other pages are written by hand and include those tables.

| Page | Content | Source |
|---|---|---|
| Home (`index.md`) | All repos, one row each | `repos.csv` |
| Organizations (`orgs.md`) | One page per organization that has a repo: its repos, packages (PyPI, npm) and images, and one page per repo below it. Empty tables and sections are left out | `jupyter_repos.json`, `images.json` |
| Published packages (`packages.md`) | A summary table, then a page with one table for PyPI and one for npm | `jupyter_repos.json` |
| Container images (`images.md`) | One table of images | `images.json` |
| About (`about.md`) | The README | `README.md` |

How the pages link to each other:

- The repo tables (home and organization pages) link each repo to its page. The `image` column shows its most
  pulled image, as `package` does for packages.
- A repo page lists its packages and its images, with links to the registries.
- The package and image tables link each row to the registry, and to its organization page and its repo page when
  there is one. On an organization page they are the same tables without the organization column. An image belongs
  to the organization of its namespace.
- Package and image tables share the columns organization, repository and last published. Usage is downloads per
  month for packages and all-time pulls for images. Only the repo tables are tinted by kind.

The class `sphinx-datatable` makes a table sortable and searchable (DataTables). `docs/_static/tables.js` hides
everything but the sorting on a table of 10 rows or fewer, and adds a filter on the column named "organization" to
the tables with the class `filter-by-org`.

Text that comes from repos or the LLM (descriptions, labels, rationales) goes through `plain()` in `insights.py`,
so it is shown as text and never becomes HTML, a link or a substitution.

## Automation

| Workflow | When | What |
|---|---|---|
| `ci.yml` | each push to `main` and each pull request | Formatting (pre-commit, ruff), the tests, and a check that `jupyter_repos.json` and `repos.csv` match the code. Steps 1 to 5 need the network or an LLM, so they are not rerun. |
| `docs.yml` | each push to `main` and each pull request; on `main` it also publishes | Builds the site with warnings as errors. |
| `update.yml` | every day | Runs steps 1 to 7, commits `output/`, then calls `docs.yml`. |

Actions are pinned to commit SHAs.

## Adding things

- **A registry namespace:** add it to `NAMESPACES` in step 4, after checking that it belongs to Jupyter. A Docker Hub
  namespace named like a Jupyter organization can belong to someone else. It must also be an organization of `ORGS`.
- **A column in the repo tables:** add it in `7_table.py` and in `repo_rows` of `insights.py`.
- **Another kind of published thing:** a new step before step 6 that writes its own file with a `repo` and a
  `reason`; read it in step 6; add a table like the package and image tables.
