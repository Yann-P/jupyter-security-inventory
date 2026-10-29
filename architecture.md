# Architecture

Two parts: a **pipeline** of six Python scripts that writes data files, and a **page** that reads them.

```
GitHub, PyPI, npm, pypistats.org, deps.dev, Docker Hub, Quay, an LLM
        │
        ▼
scripts/1..5  ──►  output/*.json  ──►  scripts/6  ──►  site/data/*.json  ──►  site/*.js  ──►  tables in the browser
 (fetch)           (one per step)      (join)          (one per entity)      (static page)
```

## Rules

- Data flows one way. A script reads only the outputs of earlier steps.
- `output/` and `site/data/` are written by the scripts only. Never edit them by hand (see Contributing in the README).
- The outputs are committed, so the page works without network access and every change shows up in git.
- The joins are done in Python, in step 6. The page only filters, sorts and follows ids.
- Inputs written by hand: `ORGS` (step 1), `NAMESPACES` (step 4), the prompt and model (step 5), the views (`site/views.js`).

## The pipeline

| Step | Script | Reads | Writes |
|---|---|---|---|
| 1 | `1_inventory.py` | `ORGS`, GitHub | `repos.json` |
| 2 | `2_scan_repos.py` | `repos.json`, GitHub clones | `scan.json` |
| 3 | `3_packages.py` | `repos.json`, `scan.json`, PyPI, npm, pypistats, deps.dev | `packages.json` |
| 4 | `4_images.py` | `NAMESPACES`, `repos.json`, `scan.json`, Docker Hub, Quay | `images.json`, `images.txt` |
| 5 | `5_classify.py` | `repos.json`, `scan.json`, `packages.json`, clones, LLM | `classification.json` |
| 6 | `6_build_dataset.py` | steps 1 to 5 | `site/data/repos.json`, `packages.json`, `images.json`, `meta.json` |

`common.py` has what the scripts share: reading and writing JSON, and `fetch_json`, which caches answers for
24 hours in `.cache/http/` and retries on rate limits (HTTP 429) and server errors.

Step 2 keeps, for each repo: the commit and date of its latest commit, file counts by type, the packages its
manifests declare, a summary of its workflows (triggers, secrets, what they publish), the actions it uses, the
images its chartpress files build, the build requirements of its `pyproject.toml`, and the start of its README. A
clone is shallow and holds only those files. Symbolic links are never followed.

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

`output/` holds the raw result of each step. Repos are named `org/repo`.

| File | Shape |
|---|---|
| `repos.json` | `fetched_on`, `orgs`, and `repos`: full_name, org, name, description, is_fork. |
| `scan.json` | `{repo: facts from step 2}`. |
| `packages.json` | `accepted`: system (PYPI or NPM), name, repo, reason, downloads_last_month, dependents, last_published. `rejected`: candidates that were not confirmed. |
| `images.json` | `images`: registry, namespace, name, tag, last_published, pulls (all time), reference, repo, reason. |
| `images.txt` | One image reference per line. |
| `classification.json` | `{repo: kind, security_boundary, deploys_live_service, rationale, model}`. Written by an LLM. |

`site/data/` holds what the page loads: one file per entity, each record with an `id`, and ids wherever it refers
to another record.

| File | Shape |
|---|---|
| `repos.json` | A list of repos: the facts of steps 1, 2 and 5, the ids of its packages and images, `used_by` and `uses`. |
| `packages.json` | A list of packages: the facts of step 3 and the id of the repo that publishes it. |
| `images.json` | A list of images: the facts of step 4 and the id of the repo it comes from, if any. |
| `meta.json` | `fetched_on` and `orgs`. |

The docstring of `6_build_dataset.py` describes the fields, and `tests/test_site_data.py` lists every one of them
with its type and checks that the ids resolve: it is the contract between the Python and the JavaScript.

`used_by` lists the other repos that run a repo's code, and `uses` is the same relation seen from the other side.
`ci`: they use its GitHub Actions in a workflow. `ci_pinned`: the same, pinned to a commit, so a compromise of the
action does not reach them by itself. `build`: they use its packages in their build requirements. "Used in CI" counts
`ci` and `build`.

## The page

`site/` is static files, served as they are: `python3 -m http.server -d site`. There is no build step and no
external request; Tabulator is copied into `site/vendor/`.

| File | What it does |
|---|---|
| `index.html`, `style.css` | The shell and the look (light and dark, down to a phone). |
| `app.js` | Loads the files in `site/data/`, indexes them by id, and routes the URL fragment to a page. |
| `views.js` | The views: one declarative object each, with its filter and columns. The only file you edit to add a table. |
| `table.js` | Draws a view's rows with Tabulator, and remembers the sort and filters. |
| `cells.js` | The cells: links to other records and to the registries, numbers, dates. |

The routes are `#/` (the views and their row counts), `#/view/<id>` (with the view's parameters in the query, like
`?days=180`), `#/repo/<org>/<name>`, `#/package/<SYSTEM:name>` and `#/org/<org>`. A repo, package or organization page
lists what it is related to, as small sortable tables, and every id is a link to the page of its record. Images have
no page of their own: they link to their registry, their repo and their organization.

Text that comes from repos, registries or the LLM (descriptions, labels, rationales) is data, not markup. The page
builds its elements with `h()` in `cells.js`, which sets text and refuses any link that is not a route of the page or
one of a few fixed registry and GitHub addresses.

## Automation

| Workflow | When | What |
|---|---|---|
| `ci.yml` | each push to `main` and each pull request | Formatting (pre-commit, ruff), the tests, the syntax of the page's JavaScript, and a check that `site/data/` matches the code. Steps 1 to 5 need the network or an LLM, so they are not rerun. |
| `update.yml` | every day | Runs steps 1 to 6 and commits `output/` and `site/data/`. |

Actions are pinned to commit SHAs. Hosting `site/` is up to you: it is plain static files.

## Adding things

- **A view:** add an object to `site/views.js`.
- **A registry namespace:** add it to `NAMESPACES` in step 4, after checking that it belongs to Jupyter. A Docker Hub
  namespace named like a Jupyter organization can belong to someone else. It must also be an organization of `ORGS`.
- **A column in a table:** add it to the view's `columns` in `site/views.js`. If the data does not have it yet, add
  the field in step 6 and in `tests/test_site_data.py`.
- **Another kind of published thing:** a new step before step 6 that writes its own file with a `repo` and a
  `reason`; join it in step 6 into its own file in `site/data/`, with an id, and add its invariants to
  `tests/test_site_data.py`; list it in `site/views.js`.
