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
            {"system": system, "name": name, "downloads_last_month": downloads, "dependents": dependents}
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
        "[[jupyterhub\\/jupyterhub](/orgs/jupyterhub/jupyterhub.md)]{.kind-package}",
        "package",
        "[1,234](https://pypistats.org/packages/jupyterhub)",
        "56",
        "[runs multi\\-user servers]{.reason}",
    ]


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


def make_image(registry, namespace, name, pulls, repos=()):
    return {
        "registry": registry,
        "namespace": namespace,
        "name": name,
        "tag": "latest",
        "pulls": pulls,
        "last_pushed": "2026-10-28",
        "repos": list(repos),
    }


def test_image_row_links_the_image_and_the_repos_it_points_to():
    data = make_data(make_repo("jupyter/docker-stacks", []))
    image = make_image("quay.io", "jupyter", "base-notebook", None, ["jupyter/docker-stacks", "gone/repo"])
    assert (
        insights.image_row(data, image)
        == [
            "[jupyter\\/base\\-notebook](https://quay.io/repository/jupyter/base-notebook)",
            "latest",
            "quay.io",
            "",  # Quay publishes no pull counts
            "2026-10-28",
            "[jupyter\\/docker\\-stacks](/orgs/jupyter/docker-stacks.md), gone\\/repo",  # a repo no longer listed is not linked
        ]
    )
    image = make_image("docker.io", "jupyterhub", "jupyterhub", 1234)
    assert insights.image_row(data, image)[:4] == [
        "[jupyterhub\\/jupyterhub](https://hub.docker.com/r/jupyterhub/jupyterhub)",
        "latest",
        "docker.io",
        "1,234",
    ]


def test_image_rows_list_the_most_pulled_first_and_the_images_without_counts_last():
    data = make_data()
    data.images = [
        make_image("quay.io", "jupyter", "a", None),
        make_image("docker.io", "jupyter", "b", 5),
        make_image("docker.io", "jupyter", "c", 9),
    ]
    assert [row[0].split("]")[0].removeprefix("[jupyter\\/") for row in insights.image_rows(data)] == ["c", "b", "a"]
