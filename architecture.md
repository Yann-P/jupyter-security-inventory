# Architecture

This project collects facts about the public repositories of Project Jupyter, and shows them as a website.
It has two parts: a **pipeline** of seven Python scripts that writes data files, and a **site** that reads them.

```
GitHub, PyPI, npm, deps.dev, Docker Hub, Quay, an LLM
        │
        ▼
scripts/1..7  ──►  output/*.json, *.csv, *.txt  ──►  docs/insights.py  ──►  Sphinx site
 (pipeline)        (committed to git)                (writes the pages)      (GitHub Pages)
```

## Rules

- Data flows one way. A script reads only the outputs of earlier steps, never of later ones.
- `output/` is written by the scripts only. Never edit it by hand. When you change a script, rerun it and the
  steps after it, and commit the new outputs with your change.
- The outputs are committed, so the site can be built without network access and every change shows up in git.
- Only a few inputs are written by hand: `ORGS` (step 1), `NAMESPACES` (step 4), the prompt and model (step 5).

## The pipeline

| Step | Script | Reads | Writes | Notes |
|---|---|---|---|---|
| 1 | `1_inventory.py` | `ORGS`, GitHub | `repos.json` | Public, non-archived, non-empty repos. |
| 2 | `2_scan_repos.py` | `repos.json`, GitHub clones | `scan.json` | Downloads only a few files per repo (see below). |
| 3 | `3_packages.py` | `repos.json`, `scan.json`, PyPI, npm, pypistats, deps.dev | `packages.json` | Which repo publishes which package. |
| 4 | `4_images.py` | `NAMESPACES`, `repos.json`, `scan.json`, Docker Hub, Quay | `images.json`, `images.txt` | Which repo builds which image. |
| 5 | `5_classify.py` | `repos.json`, `scan.json`, `packages.json`, clones, LLM | `classification.json` | Labels each repo once. |
| 6 | `6_build_dataset.py` | steps 1 to 5 | `jupyter_repos.json` | One record per repo, with everything about it. |
| 7 | `7_table.py` | `jupyter_repos.json` | `repos.csv` | One row per repo. |

`common.py` holds what the scripts share: reading and writing JSON, and `fetch_json`, which caches answers for
24 hours in `.cache/http/` and retries on rate limits (HTTP 429) and server errors.

### What step 2 keeps

For each repo: file counts by type, the packages its manifests declare, a summary of its workflows (triggers,
secrets, what they publish), the actions it uses, the images its chartpress files build, the build requirements of
its `pyproject.toml`, and the start of its README. Clones are shallow and hold no file contents except these files.
Symbolic links are never followed.

### How things are matched to repos

A package or an image is matched to the repo it comes from, and the match always carries a `reason`.

- **Package → repo** (step 3): a manifest declares the package, and PyPI or npm confirms it (it links to the repo,
  or the names and owners fit). If several repos declare it, the one the registry links to wins.
- **Image → repo** (step 4), first match wins: the repo's chartpress file builds the image; the registry description
  links to the repo; the repo is named like the image. Many older images match nothing, and have no repo.
- Forks never count in either match: a fork has the files of its original, but does not publish.
- **Image → organization**: its registry namespace. Each namespace in `NAMESPACES` must be a GitHub organization
  of `ORGS`; step 4 stops if not.

## The data files

All in `output/`. Repos are named `org/repo`.

| File | Shape |
|---|---|
| `repos.json` | `orgs`, and `repos`: name, org, description, is_fork. |
| `scan.json` | `{repo: facts from step 2}`. |
| `packages.json` | `accepted`: system (PYPI or NPM), name, repo, reason, downloads_last_month, dependents, last_published. `rejected`: candidates that were not confirmed. |
| `images.json` | `images`: registry, namespace, name, tag, reference, digest, last_published, pulls (all time), repo, reason. |
| `images.txt` | One image reference per line, for image scanners. Nothing else is in it. |
| `classification.json` | `{repo: kind, security_boundary, deploys_live_service, rationale, model}`. Written by an LLM. |
| `jupyter_repos.json` | The repo from step 1, plus its packages, images, content, `used_by` and classification. |
| `repos.csv` | The columns of the home page table. |

`used_by` (step 6) says which other repos run a repo's code: through its GitHub Actions in their workflows (`ci`, or
`ci_pinned` when pinned to a commit, which is safe from a compromise), or through its packages in their build
requirements (`build`).

## The site

`docs/conf.py` calls `insights.build()` every time Sphinx starts. It reads `output/` and writes the CSV tables to
`docs/_generated/` and a page per organization and repository to `docs/orgs/`. Both folders are generated and not
committed. The other pages are written by hand and include those tables.

| Page | Content | Source |
|---|---|---|
| Home (`index.md`) | All repos, one row each | `repos.csv` |
| Organizations (`orgs.md`) | One page per organization: its repos, its packages (PyPI, npm) and its images. One page per repo below it | `jupyter_repos.json`, `packages.json`, `images.json` |
| Published packages (`packages.md`) | A summary, then one table for PyPI and one for npm | `packages.json` |
| Container images (`images.md`) | One table of images | `images.json` |
| About (`about.md`) | The README | `README.md` |

How the pages link to each other:

- A repo table (home and organization pages) links each repo to its page. The `images` column counts its images.
- An organization page has the repo tables, then the tables of its packages and images. They are the same tables as
  the package and image pages, without the organization column. An image belongs to the organization of its namespace.
- A repo page lists its packages and its images, with links to the registries.
- The package and image tables link each row to the registry, to its organization page and to its repo page.
- Package and image tables have the same columns: what, organization, repository, usage, last published. They have
  an organization filter. Only the repo tables are tinted by kind.
- Usage is not the same everywhere: downloads per month for packages, all-time pulls for images.

`docs/_static/tables.js` adds sorting, search and the organization filter (it filters the column named
"organization") to the tables with the class `sphinx-datatable`. The filter needs the class `filter-by-org`.

## Safety of the site

Text that comes from repos or from the LLM (descriptions, labels, rationales) can hold anything. It goes through
`plain()` in `insights.py`, so it is shown as text and never becomes HTML, a link or a substitution.

## Automation

| Workflow | When | What |
|---|---|---|
| `ci.yml` | each push and pull request | Formatting (pre-commit, ruff), the tests, and a check that `jupyter_repos.json` and `repos.csv` match the code. Steps 1 to 5 need the network or an LLM, so they are not rerun. |
| `docs.yml` | each push and pull request; on `main` it also publishes | Builds the site with warnings as errors. |
| `update.yml` | every day | Runs steps 1 to 7, commits `output/`, then calls `docs.yml`. |

Actions are pinned to commit SHAs. Step 5 labels only new repos, so a daily run costs almost nothing.

## Limits to keep in mind

- Packages are found from the repos, so a package whose repo is not in the inventory is not seen.
- Labels (`kind`, `security_boundary`) come from an LLM and can be wrong.
- Download counts include CI.
- Images: ghcr.io is not covered, Quay has no pull counts, and only one tag per image is recorded.
- "Used in CI" sees only the repos of this inventory.

## Adding things

- **A registry namespace:** add it to `NAMESPACES` in step 4, after checking that it really belongs to Jupyter.
  Docker Hub namespaces named like a Jupyter organization sometimes belong to someone else.
- **A column in the home table:** add it in `7_table.py` and in `repo_rows` of `insights.py`.
- **A new kind of published thing** (for example another registry): a new step before step 5 that writes its own
  file with a `repo` and a `reason`; add it to step 6; add a table that has the same columns as the others.
