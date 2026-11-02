"""Tests for docs/insights.py, which writes the site's pages."""

import insights


def test_plain_keeps_text_from_repos_from_becoming_html_or_markdown():
    assert insights.plain("<script>") == "\\<script\\>"
    assert insights.plain("{{ repos }}") == "\\{\\{ repos \\}\\}"
    assert insights.plain("[click](evil)") == "\\[click\\]\\(evil\\)"  # a link the model was tricked into writing


def test_summary_sentence_reads_as_one_sentence():
    counts = {"repos": 35, "packaged": 6, "boundaries": 1, "services": 0}
    assert insights.summary_sentence("[github.com/jupyter-book](https://github.com/jupyter-book)", counts) == (
        "[github.com/jupyter-book](https://github.com/jupyter-book) has 35 public repositories: "
        "6 publish a package and 1 is a security boundary."
    )


def test_a_table_writes_its_cells_for_the_page_and_its_values_for_the_download(tmp_path, monkeypatch):
    monkeypatch.setattr(insights, "GENERATED", tmp_path)
    table = insights.Table(
        ["repo", "organization", "downloads/month"],
        [["o/r", "o", 1234]],
        [["[o\\/r](/orgs/o/r.md)", "[o](/orgs/o.md)", "1,234"]],
    )
    table.without_org().write("o-repos")
    assert (tmp_path / "o-repos.csv").read_text() == 'repo,downloads/month\n[o\\/r](/orgs/o/r.md),"1,234"\n'
    assert (tmp_path / "downloads" / "o-repos.csv").read_text() == "repo,downloads/month\no/r,1234\n"


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


def test_package_table_has_the_values_and_the_links_of_a_package():
    data = make_data(make_repo("jupyterhub/jupyterhub", [("PYPI", "jupyterhub", 1234, 56)], "runs multi-user servers"))
    table = insights.package_table(data, "PYPI", ["jupyterhub/jupyterhub"])
    assert table.rows == [["jupyterhub", "jupyterhub", "jupyterhub/jupyterhub", 1234, 56, "2026-10-20"]]
    assert table.cells == [
        [
            "[jupyterhub](https://pypi.org/project/jupyterhub/)",
            "[jupyterhub](/orgs/jupyterhub.md)",
            "[jupyterhub\\/jupyterhub](/orgs/jupyterhub/jupyterhub.md)",
            "[1,234](https://pypistats.org/packages/jupyterhub)",
            "56",
            "[2026-10-20]{.date}",
        ]
    ]


def test_image_table_leaves_unknown_pulls_and_repository_empty():
    image = {
        "registry": "quay.io",
        "namespace": "jupyterhub",
        "name": "k8s-binderhub",
        "tag": "1.0.0",
        "pulls": None,
        "last_published": "2026-07-01",
        "repo": None,
    }
    cells = dict(zip(insights.IMAGE_HEADER, insights.image_table([image]).cells[0]))
    assert (cells["all-time pulls"], cells["repository"]) == ("", "")


def test_image_table_lists_the_most_pulled_first_and_the_images_without_pull_counts_last():
    base = {"namespace": "o", "tag": "1", "last_published": None, "repo": None}
    table = insights.image_table(
        [
            base | {"registry": "quay.io", "name": "a", "pulls": None},
            base | {"registry": "docker.io", "name": "b", "pulls": 5},
            base | {"registry": "docker.io", "name": "c", "pulls": 9},
        ]
    )
    assert [row[5] for row in table.rows] == [9, 5, None]


def test_package_summary_counts_the_packages_of_each_registry():
    data = make_data(
        make_repo("jupyterlab/lumino", [("NPM", "@lumino/coreutils", 5, 1), ("NPM", "@lumino/algorithm", 9, 1)]),
        make_repo("jupyter/notebook", [("PYPI", "notebook", 7, 3)]),
    )
    assert [row[:4] for row in insights.package_summary(data).cells] == [
        ["[PyPI](/packages/pypi.md)", 1, 1, 1],
        ["[npm](/packages/npm.md)", 2, 1, 1],
    ]


def test_sections_leave_out_empty_tables_and_the_sections_they_were_in():
    body = insights.sections("o", [["r"]], [], {"PyPI": [], "npm": [["p"]]}, [], by_org=False)
    headings = [line for line in body.splitlines() if line.startswith("#")]
    assert headings == ["## Repositories", "### Software", "## Packages", "### npm"]
    assert body.startswith("[Repositories (1)](#repositories) · [Packages (1)](#packages)")  # no link to "Images"
    assert "filter-by-org" not in body  # an organization's tables have no organization column to filter

    body = insights.sections("o", [["r"]], [["d"]], {"PyPI": [], "npm": []}, [], by_org=False)
    assert "(#" not in body  # a page with one section needs no links to its sections


def test_sections_list_the_images_without_a_subheading():
    body = insights.sections("all", [["r"]], [], {"PyPI": [], "npm": []}, [["i"], ["j"]], by_org=True)
    headings = [line for line in body.splitlines() if line.startswith("#")]
    assert headings == ["## Repositories", "### Software", "## Images"]
    assert body.startswith("[Repositories (1)](#repositories) · [Images (2)](#images)")
    assert ":class: sphinx-datatable filter-by-org" in body  # the images have an organization column here
