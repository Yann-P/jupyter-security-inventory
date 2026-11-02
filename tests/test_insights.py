"""Tests for docs/insights.py, which writes the site's pages."""

import insights
from topics import STATUSES


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
    body = insights.sections("o", [], [["r"]], [], {"PyPI": [], "npm": [["p"]]}, [], by_org=False)
    headings = [line for line in body.splitlines() if line.startswith("#")]
    assert headings == ["## Repositories", "### Software", "## Packages", "### npm"]
    assert body.startswith("[Repositories (1)](#repositories) · [Packages (1)](#packages)")  # no link to "Images"
    assert "filter-by-org" not in body  # an organization's tables have no organization column to filter

    body = insights.sections("o", [], [["r"]], [["d"]], {"PyPI": [], "npm": []}, [], by_org=False)
    assert "(#" not in body  # a page with one section needs no links to its sections


def test_sections_list_the_images_without_a_subheading():
    body = insights.sections("all", [], [["r"]], [], {"PyPI": [], "npm": []}, [["i"], ["j"]], by_org=True)
    headings = [line for line in body.splitlines() if line.startswith("#")]
    assert headings == ["## Repositories", "### Software", "## Images"]
    assert body.startswith("[Repositories (1)](#repositories) · [Images (2)](#images)")
    assert ":class: sphinx-datatable filter-by-org" in body  # the images have an organization column here


def test_sections_start_with_the_security_topics_and_link_to_them():
    body = insights.sections("o", [["t"]], [["r"]], [], {"PyPI": [], "npm": []}, [], by_org=False)
    assert body.startswith("[Security topics (1)](#security-topics) · [Repositories (1)](#repositories)")
    assert body.index("## Security topics") < body.index("## Repositories")


def test_the_statuses_are_the_ones_the_topics_use():
    assert insights.STATUSES == list(STATUSES)


def make_topic_data():
    """Three repos and one topic: a is done, b is missing, c is not applicable, d is partial."""
    answers = {
        "a/one": ("done", ["GitHub Action"], "Runs in a workflow.", [".github/workflows/z.yml"]),
        "b/two": ("missing", [], "No sign of it.", []),
        "c/three": ("n/a", [], "No workflows.", []),
        "b/four": ("partial", ["pre-commit"], "Hook only.", [".pre-commit-config.yaml"]),
    }
    data = make_data(
        *(
            make_repo(name, [("PYPI", name.split("/")[1], downloads, 0)])
            for name, downloads in (("a/one", 5), ("b/two", 9), ("c/three", 1), ("b/four", 3))
        )
    )
    for repo in data.repos.values():
        repo["content"] = {"commit": "c0ffee"}
        repo["top_package"] = "PYPI:x"
        repo["max_downloads_last_month"] = repo["packages"][0]["downloads_last_month"]
        repo["used_by"] = {"ci": [], "build": [], "ci_pinned": []}
    data.orgs = ["a", "b", "c"]
    data.topics = [
        {
            "id": "t",
            "title": "t",
            "question": "Is it?",
            "detection": "We look.",
            "meanings": dict.fromkeys(STATUSES, "Means."),
        }
    ]
    data.results = {
        "t": {name: dict(zip(("status", "via", "reason", "evidence"), a), repo=name) for name, a in answers.items()}
    }
    data.history = {
        "2026-11-01": {"t": {"done": 0, "partial": 0, "missing": 4, "n/a": 0}},
        "2026-11-02": {"t": {"done": 1, "partial": 1, "missing": 1, "n/a": 1}},
        "2026-11-03": {"t": {"done": 1, "partial": 1, "missing": 1, "n/a": 1}},  # nothing changed
    }
    return data


def test_topic_summary_counts_the_statuses_of_the_repos_it_is_given():
    data = make_topic_data()
    assert insights.topic_summary(data, ["a/one", "b/two", "c/three", "b/four"]).rows == [["t", "Is it?", 1, 1, 1, 1]]
    assert insights.topic_summary(data, ["b/two"]).rows == [["t", "Is it?", 0, 0, 1, 0]]
    assert insights.topic_summary(data, ["b/two"]).cells[0][0] == "[t](/topics/t.md)"


def test_topic_org_table_lists_the_organizations_with_the_most_left_to_do_first():
    table = insights.topic_org_table(make_topic_data(), make_topic_data().topics[0])
    assert table.rows == [["b", 2, 0, 1, 1], ["a", 1, 1, 0, 0]]  # c has nothing it applies to


def test_topic_repo_table_leaves_out_what_is_not_applicable_and_lists_the_done_ones_last():
    data = make_topic_data()
    table = insights.topic_repo_table(data, data.topics[0])
    assert [row[:3] for row in table.rows] == [
        ["b/two", "b", "missing"],  # most downloaded of those with something to do
        ["b/four", "b", "partial"],
        ["a/one", "a", "done"],
    ]
    assert table.rows[2][3:] == ["GitHub Action", 5, "Runs in a workflow.", ".github/workflows/z.yml"]
    assert (
        table.cells[2][-1]
        == "[\\.github\\/workflows\\/z\\.yml](https://github.com/a/one/blob/c0ffee/.github/workflows/z.yml)"
    )


def test_topic_history_lists_only_the_days_the_numbers_changed_newest_first():
    data = make_topic_data()
    assert insights.topic_history_table(data, data.topics[0]).rows == [
        ["2026-11-02", 1, 1, 1, 1],
        ["2026-11-01", 0, 0, 4, 0],
    ]


def test_topic_headline_counts_what_it_applies_to_and_what_is_left_out():
    counts = insights.Counter({"done": 5, "partial": 0, "missing": 279, "n/a": 154})
    assert insights.topic_headline(counts) == (
        "It applies to 284 repositories: 5 done, 0 partial and 279 missing. 154 are not applicable and left out of the tables."
    )
    assert insights.topic_headline(insights.Counter({"missing": 1, "n/a": 1})).endswith(
        "1 repository: 0 done, 0 partial and 1 missing. 1 is not applicable and left out of the tables."
    )


def test_repo_topics_shows_text_from_a_repo_as_text():
    data = make_topic_data()
    data.results["t"]["a/one"]["reason"] = "[click](https://evil.example)"
    data.results["t"]["a/one"]["evidence"] = ["a b.yml"]
    line = insights.repo_topics(data, "a/one")
    assert "[click](" not in line  # the link was not made
    assert "blob/c0ffee/a%20b.yml" in line  # the path is quoted in the URL
