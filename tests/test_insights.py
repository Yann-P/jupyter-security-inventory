"""Tests for docs/insights.py, which writes the site's pages."""

import insights


def test_plain_keeps_text_from_repos_from_becoming_html_or_markdown():
    assert insights.plain("<script>") == "\\<script\\>"
    assert insights.plain("{{ repos }}") == "\\{\\{ repos \\}\\}"
    assert insights.plain("[click](evil)") == "\\[click\\]\\(evil\\)"  # a link the model was tricked into writing


def test_org_summary_reads_as_one_sentence():
    counts = {"repos": 35, "packaged": 6, "boundaries": 1, "services": 0}
    assert insights.org_summary("jupyter-book", counts) == (
        "[github.com/jupyter-book](https://github.com/jupyter-book) has 35 public repositories: "
        "6 publish a package and 1 is a security boundary."
    )


def make_data(*repos):
    """A Data with just these repos, instead of everything in output/."""
    data = insights.Data.__new__(insights.Data)
    data.repos = {repo["full_name"]: repo for repo in repos}
    return data


def make_repo(full_name, packages, boundary=None):
    org = full_name.split("/")[0]
    return {
        "full_name": full_name,
        "org": org,
        "packages": [
            {
                "system": system,
                "name": name,
                "downloads_last_month": downloads,
                "dependents": dependents,
                "last_published": "2026-10-20",
            }
            for system, name, downloads, dependents in packages
        ],
        "classification": {"kind": "package", "security_boundary": boundary},
    }


def test_registry_url_keeps_the_scope_of_an_npm_package_readable():
    assert insights.registry_url("NPM:@lumino/coreutils") == "https://www.npmjs.com/package/@lumino/coreutils"
    assert insights.registry_url("PYPI:jupyter_core") == "https://pypi.org/project/jupyter_core/"


def test_published_lists_one_registry_most_downloaded_first():
    data = make_data(
        make_repo("jupyterlab/lumino", [("NPM", "@lumino/coreutils", 5, 1), ("NPM", "@lumino/algorithm", 9, 1)]),
        make_repo("jupyter/notebook", [("PYPI", "notebook", 7, 3), ("NPM", "@jupyter-notebook/app", None, None)]),
    )
    assert [(repo, p["name"]) for repo, p in insights.published(data, "NPM")] == [
        ("jupyterlab/lumino", "@lumino/algorithm"),
        ("jupyterlab/lumino", "@lumino/coreutils"),
        ("jupyter/notebook", "@jupyter-notebook/app"),  # unknown downloads come last
    ]
    assert [p["name"] for _, p in insights.published(data, "PYPI")] == ["notebook"]


def test_package_row_links_the_package_its_org_and_its_repo():
    data = make_data(make_repo("jupyterhub/jupyterhub", [("PYPI", "jupyterhub", 1234, 56)], "runs multi-user servers"))
    [(name, package)] = insights.published(data, "PYPI")
    assert insights.package_row(data, name, package) == [
        "[jupyterhub](https://pypi.org/project/jupyterhub/)",
        "[jupyterhub](/orgs/jupyterhub.md)",
        "[jupyterhub\\/jupyterhub](/orgs/jupyterhub/jupyterhub.md)",
        "[1,234](https://pypistats.org/packages/jupyterhub)",
        "56",
        "[2026-10-20]{.date}",
    ]


def test_image_row_leaves_unknown_pulls_and_repository_empty():
    image = {
        "registry": "quay.io",
        "namespace": "jupyterhub",
        "name": "k8s-binderhub",
        "tag": "1.0.0",
        "pulls": None,
        "last_published": "2026-07-01",
        "repo": None,
    }
    row = dict(zip(insights.IMAGE_HEADER, insights.image_row(image)))
    assert (row["all-time pulls"], row["repository"]) == ("", "")


def test_image_rows_list_the_most_pulled_first_and_the_images_without_pull_counts_last():
    base = {"namespace": "o", "tag": "1", "last_published": None, "repo": None}
    rows = insights.image_rows(
        [
            base | {"registry": "quay.io", "name": "a", "pulls": None},
            base | {"registry": "docker.io", "name": "b", "pulls": 5},
            base | {"registry": "docker.io", "name": "c", "pulls": 9},
        ]
    )
    assert [row[5] for row in rows] == ["9", "5", ""]


def test_package_pages_write_a_table_per_registry_and_summarize_them(tmp_path, monkeypatch):
    monkeypatch.setattr(insights, "GENERATED", tmp_path)
    data = make_data(
        make_repo("jupyterlab/lumino", [("NPM", "@lumino/coreutils", 5, 1), ("NPM", "@lumino/algorithm", 9, 1)]),
        make_repo("jupyter/notebook", [("PYPI", "notebook", 7, 3)]),
    )
    summary = insights.package_pages(data)
    assert [row[:4] for row in summary] == [
        ["[PyPI](/packages/pypi.md)", 1, 1, 1],
        ["[npm](/packages/npm.md)", 2, 1, 1],
    ]
    assert len((tmp_path / "packages-pypi.csv").read_text().splitlines()) == 2  # the header and notebook
    assert len((tmp_path / "packages-npm.csv").read_text().splitlines()) == 3


def test_org_body_leaves_out_empty_tables_and_the_sections_they_were_in():
    body = insights.org_body("o", software=[["r"]], docs=[], packages={"PyPI": [], "npm": [["p"]]}, images=[])
    headings = [line for line in body.splitlines() if line.startswith("#")]
    assert headings == ["## Repositories", "### Software", "## Packages", "### npm"]
    assert body.startswith("[Repositories (1)](#repositories) · [Packages (1)](#packages)")  # no link to "Images"

    body = insights.org_body("o", software=[["r"]], docs=[["d"]], packages={"PyPI": [], "npm": []}, images=[])
    assert "(#" not in body  # a page with one section needs no links to its sections


def test_org_body_lists_the_images_under_their_section_without_a_subheading():
    body = insights.org_body("o", software=[["r"]], docs=[], packages={"PyPI": [], "npm": []}, images=[["i"], ["j"]])
    headings = [line for line in body.splitlines() if line.startswith("#")]
    assert headings == ["## Repositories", "### Software", "## Images"]
    assert body.startswith("[Repositories (1)](#repositories) · [Images (2)](#images)")
