"""What the web page relies on in site/data/*.json, the files written by scripts/6_build_dataset.py.

Read this file to learn the data model (the docstring of scripts/6_build_dataset.py says how the fields are made).
The page follows every cross-reference with one lookup by id and shows the fields as they are, so what must hold is:

  - ids are unique, and every id found in a field (package.repo, repo.packages, image.repo, repo.images, used_by,
    uses) is the id of a record that exists;
  - a fact is never stored twice differently: package.repo and repo.packages agree (so do image.repo and
    repo.images), used_by and uses are inverses, and the counts are derived from the lists they sit next to;
  - every field has the type below on every record. "| None" marks the fields that may be null, and the comment
    says when. Dates are YYYY-MM-DD strings.

The tests read the committed files, so they check what the page will load. When you add a field or an inventory,
add it here: this file is the contract between the Python that joins the data and the JavaScript that shows it.
"""

import datetime
import re
from typing import get_args

import pytest
from common import SITE_DATA, load_json, prose_ratio

# repos.json: one record per public repo. Required fields and their types.
REPO_FIELDS = {
    "id": str,  # "org/name", e.g. "jupyterlab/jupyterlab"; how everything else refers to the repo
    "org": str,  # the GitHub organization; one of meta.orgs
    "name": str,
    "description": str | None,  # None when the repo has no description on GitHub
    "is_fork": bool,
    "kind": str,  # what the language model decided it is; one of KINDS
    "live_service": str | None,  # the site or service it deploys; None when it deploys none
    "security_boundary": str | None,  # why its bugs can be exploited over the network; None when they cannot
    "rationale": str,  # why the model chose these labels
    "packages": list,  # ids of the packages it publishes, the most downloaded first
    "images": list,  # ids of the container images built from it, the most pulled first
    "downloads_last_month": int | None,  # of its most downloaded package; None when it publishes no package
    "dependents": int | None,  # same
    "pulls": int | None,  # all-time pulls of its most pulled image; None when it has no image or no pull counts
    "used_by": dict,  # who runs its code, as {USE: [repo ids]}
    "uses": dict,  # whose code it runs: used_by seen from the other side, as {USE: [repo ids]}
    "used_in_ci": int,  # how many repos run its code unpinned: the union of used_by.ci and used_by.build
    "workflows": dict,  # what its GitHub Actions workflows do, see WORKFLOW_FIELDS
    "n_files": int,
    "file_types": dict,  # {type of file: how many}, the types are in FILE_TYPES
    "prose_ratio": float | None,  # share of docs, notebooks, web pages and media among those and code; None if none
    "head": str,  # the commit that was scanned: 40 hex digits
    "last_commit": str | None,  # date of the latest commit; None when the scan did not record it
}

# packages.json: one record per PyPI or npm package that belongs to one of the repos.
PACKAGE_FIELDS = {
    "id": str,  # "SYSTEM:name", e.g. "PYPI:jupyterlab" or "NPM:@jupyterlab/application"
    "system": str,  # PYPI or NPM
    "name": str,
    "repo": str,  # id of the repo that publishes it
    "reason": str,  # why step 3 matched the package to that repo
    "downloads_last_month": int | None,  # None when pypistats.org or npm do not know the package
    "dependents": int | None,  # None when deps.dev does not know the package
    "last_published": str | None,  # date of its newest version; None when deps.dev does not know the package
}

# images.json: one record per container image of the registry namespaces listed in scripts/4_images.py.
IMAGE_FIELDS = {
    "id": str,  # "registry/org/name", e.g. "quay.io/jupyterhub/k8s-hub"; the tag is not part of it
    "registry": str,  # docker.io or quay.io
    "org": str,  # the registry namespace, which step 4 makes sure is a GitHub organization of meta.orgs
    "name": str,
    "tag": str,  # the one that was recorded: latest, or the newest tag if there is no latest
    "reference": str,  # what to pull: id:tag
    "repo": str | None,  # id of the repo it is built from; None when no repo matches (many older images)
    "reason": str | None,  # why step 4 matched it to that repo; None exactly when repo is None
    "pulls": int | None,  # all time; None on Quay, which has no pull counts
    "last_published": str,  # date of the tag
}

# meta.json: the one record that describes the others.
META_FIELDS = {
    "fetched_on": str,  # the day the data was fetched; the page takes it as "today" to tell what is stale
    "orgs": list,  # every organization that was inventoried, including those with no repo to list
}

SYSTEMS = {"PYPI", "NPM"}
REGISTRIES = {"docker.io", "quay.io"}
KINDS = {
    "package",
    "application",
    "tooling",
    "deployment",
    "documentation",
    "example",
    "other",
}  # scripts/5_classify.py
FILE_TYPES = {"code", "docs", "notebook", "web", "media", "data", "config", "other"}  # scripts/2_scan_repos.py
USES = ("ci", "ci_pinned", "build")  # the ways a repo can run another's code, see scripts/6_build_dataset.py
WORKFLOW_FIELDS = {"count": int, "triggers": list, "secrets": list, "publishes": list}  # the lists hold strings
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@pytest.fixture(scope="module")
def repos():
    return load_json(SITE_DATA / "repos.json")


@pytest.fixture(scope="module")
def packages():
    return load_json(SITE_DATA / "packages.json")


@pytest.fixture(scope="module")
def images():
    return load_json(SITE_DATA / "images.json")


@pytest.fixture(scope="module")
def meta():
    return load_json(SITE_DATA / "meta.json")


def by_id(records):
    return {record["id"]: record for record in records}


def is_date(value):
    """YYYY-MM-DD and a day that exists (not 2026-02-30)."""
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return DATE.fullmatch(value) is not None


def type_errors(record, fields):
    """What is wrong with the record's fields, one sentence each. An exact type match: True is not an int."""
    errors = []
    for field, declared in fields.items():
        allowed = get_args(declared) or (declared,)  # "str | None" -> (str, NoneType)
        if field not in record:
            errors.append(f"{field} is missing")
        elif type(record[field]) not in allowed:
            errors.append(f"{field} is a {type(record[field]).__name__}, expected {declared}")
    return errors


# --- The shape of the records ---


def test_every_record_has_its_fields_with_the_right_types(repos, packages, images, meta):
    errors = {}
    files = (
        ("repos", repos, REPO_FIELDS),
        ("packages", packages, PACKAGE_FIELDS),
        ("images", images, IMAGE_FIELDS),
        ("meta", [meta], META_FIELDS),
    )
    for name, records, fields in files:
        for record in records:
            if problems := type_errors(record, fields):
                errors[f"{name} {record.get('id', '')}".strip()] = problems
    assert errors == {}


def test_the_files_hold_data(repos, packages, images):
    # An empty file would pass every other test.
    assert repos
    assert packages
    assert images


def test_ids_are_unique(repos, packages, images):
    assert len({repo["id"] for repo in repos}) == len(repos)
    assert len({package["id"] for package in packages}) == len(packages)
    assert len({image["id"] for image in images}) == len(images)


def test_ids_say_what_they_identify(repos, packages, images):
    for repo in repos:
        assert repo["id"] == f"{repo['org']}/{repo['name']}"
    for package in packages:
        assert package["id"] == f"{package['system']}:{package['name']}"
        assert package["system"] in SYSTEMS
    for image in images:
        assert image["id"] == f"{image['registry']}/{image['org']}/{image['name']}"
        assert image["reference"] == f"{image['id']}:{image['tag']}"
        assert image["registry"] in REGISTRIES


def test_labels_and_counts_come_from_the_known_values(repos):
    for repo in repos:
        assert repo["kind"] in KINDS, repo["id"]
        assert set(repo["file_types"]) <= FILE_TYPES, repo["id"]
        assert all(type(n) is int and n >= 0 for n in repo["file_types"].values()), repo["id"]
        assert repo["n_files"] == sum(repo["file_types"].values()), repo["id"]
        assert re.fullmatch(r"[0-9a-f]{40}", repo["head"]), repo["id"]


def test_workflows_have_a_count_and_lists_of_names(repos):
    for repo in repos:
        workflows = repo["workflows"]
        assert type_errors(workflows, WORKFLOW_FIELDS) == [], repo["id"]
        assert set(workflows) == set(WORKFLOW_FIELDS), repo["id"]
        for field in ("triggers", "secrets", "publishes"):
            assert all(type(name) is str for name in workflows[field]), repo["id"]


def test_prose_ratio_is_derived_from_the_file_types(repos):
    for repo in repos:
        assert repo["prose_ratio"] == prose_ratio(repo["file_types"]), repo["id"]


def test_dates_are_iso_days_when_they_are_not_null(repos, packages, images, meta):
    dates = [("meta", meta["fetched_on"])]
    dates += [(repo["id"], repo["last_commit"]) for repo in repos]
    dates += [(package["id"], package["last_published"]) for package in packages]
    dates += [(image["id"], image["last_published"]) for image in images]
    assert [who for who, date in dates if date is not None and not is_date(date)] == []


def test_counts_are_not_negative(repos, packages, images):
    for package in packages:
        assert (package["downloads_last_month"] or 0) >= 0, package["id"]
        assert (package["dependents"] or 0) >= 0, package["id"]
    for image in images:
        assert (image["pulls"] or 0) >= 0, image["id"]
    for repo in repos:
        assert repo["used_in_ci"] >= 0, repo["id"]
        assert repo["workflows"]["count"] >= 0, repo["id"]


# --- Repos and the packages they publish ---


def test_every_package_belongs_to_a_repo_that_lists_it(repos, packages):
    repo_by_id = by_id(repos)
    for package in packages:
        assert package["repo"] in repo_by_id, f"{package['id']} belongs to {package['repo']}, which does not exist"
        assert package["id"] in repo_by_id[package["repo"]]["packages"], package["id"]


def test_every_package_a_repo_lists_exists_and_points_back_to_it(repos, packages):
    package_by_id = by_id(packages)
    for repo in repos:
        for package_id in repo["packages"]:
            assert package_id in package_by_id, f"{repo['id']} lists {package_id}, which does not exist"
            assert package_by_id[package_id]["repo"] == repo["id"], f"{package_id} is listed by {repo['id']}"


def test_a_repo_shows_the_numbers_of_its_most_downloaded_package(repos, packages):
    package_by_id = by_id(packages)
    for repo in repos:
        mine = [package_by_id[package_id] for package_id in repo["packages"]]
        downloads = [package["downloads_last_month"] or 0 for package in mine]
        assert downloads == sorted(downloads, reverse=True), f"{repo['id']}: packages are not sorted by downloads"
        if mine:
            assert repo["downloads_last_month"] == downloads[0], repo["id"]
            assert repo["dependents"] == (mine[0]["dependents"] or 0), repo["id"]
        else:
            assert repo["downloads_last_month"] is None, repo["id"]
            assert repo["dependents"] is None, repo["id"]


# --- Repos and the images built from them ---


def test_an_image_has_a_reason_exactly_when_it_has_a_repo(images):
    assert [i["id"] for i in images if (i["repo"] is None) != (i["reason"] is None)] == []


def test_every_image_belongs_to_a_repo_that_lists_it_or_to_none(repos, images):
    repo_by_id = by_id(repos)
    for image in images:
        if image["repo"] is not None:
            assert image["repo"] in repo_by_id, f"{image['id']} comes from {image['repo']}, which does not exist"
            assert image["id"] in repo_by_id[image["repo"]]["images"], image["id"]


def test_every_image_a_repo_lists_exists_and_points_back_to_it(repos, images):
    image_by_id = by_id(images)
    for repo in repos:
        for image_id in repo["images"]:
            assert image_id in image_by_id, f"{repo['id']} lists {image_id}, which does not exist"
            assert image_by_id[image_id]["repo"] == repo["id"], f"{image_id} is listed by {repo['id']}"


def test_a_repo_shows_the_pulls_of_its_most_pulled_image(repos, images):
    image_by_id = by_id(images)
    for repo in repos:
        pulls = [image_by_id[image_id]["pulls"] or 0 for image_id in repo["images"]]
        assert pulls == sorted(pulls, reverse=True), f"{repo['id']}: images are not sorted by pulls"
        assert repo["pulls"] == (image_by_id[repo["images"][0]]["pulls"] if pulls else None), repo["id"]


# --- Who runs whose code ---


def test_used_by_and_uses_list_repo_ids_in_every_kind_of_use(repos):
    ids = set(by_id(repos))
    for repo in repos:
        for side in ("used_by", "uses"):
            assert set(repo[side]) == set(USES), f"{repo['id']}.{side} must have exactly the keys {USES}"
            for use, others in repo[side].items():
                where = f"{repo['id']}.{side}.{use}"
                assert others == sorted(set(others)), f"{where} is not sorted without duplicates"
                assert set(others) <= ids, f"{where} has ids that are no repo: {set(others) - ids}"
                assert repo["id"] not in others, f"{where} has the repo itself"


def test_uses_is_used_by_seen_from_the_other_side(repos):
    provided = {
        (provider["id"], use, consumer) for provider in repos for use in USES for consumer in provider["used_by"][use]
    }
    consumed = {
        (provider, use, consumer["id"]) for consumer in repos for use in USES for provider in consumer["uses"][use]
    }
    assert provided == consumed


def test_a_consumer_is_pinned_or_not_never_both(repos):
    # ci_pinned holds the consumers whose every reference is pinned to a commit; any other reference puts them in ci.
    for repo in repos:
        assert set(repo["used_by"]["ci"]).isdisjoint(repo["used_by"]["ci_pinned"]), repo["id"]


def test_used_in_ci_counts_each_unpinned_consumer_once(repos):
    for repo in repos:
        used_by = repo["used_by"]
        assert repo["used_in_ci"] == len(set(used_by["ci"]) | set(used_by["build"])), repo["id"]


# --- The organizations ---


def test_every_repo_and_image_is_in_an_organization_listed_in_meta(repos, images, meta):
    assert meta["orgs"], "meta.orgs is empty"
    assert all(type(org) is str for org in meta["orgs"])
    assert {repo["org"] for repo in repos} <= set(meta["orgs"])
    assert {image["org"] for image in images} <= set(meta["orgs"])
