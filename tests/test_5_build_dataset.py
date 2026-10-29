"""Tests for scripts/5_build_dataset.py."""

import importlib
import json

build = importlib.import_module("5_build_dataset")


def test_find_users_sees_actions_pinned_or_not_and_build_requirements():
    repos = [{"full_name": "o/tool"}, {"full_name": "o/app"}]
    scan = {
        "o/tool": {"uses": [], "build_requires": []},
        # o/app uses o/tool's action twice (once by tag, once pinned to a commit) and builds with its package.
        "o/app": {"uses": ["o/tool@v1", "O/Tool@" + "a" * 40], "build_requires": ["o_lib"]},
    }
    packages = [{"system": "PYPI", "name": "o-lib", "repo": "o/tool"}]

    ci_refs, build_users = build.find_users(repos, scan, packages)
    assert ci_refs == {"o/tool": {"o/app": [False, True]}}  # was each reference pinned?
    assert build_users == {"o/tool": {"o/app"}}


def test_the_dates_reach_the_site_and_every_reference_resolves(tmp_path, monkeypatch):
    output, site = tmp_path / "output", tmp_path / "site"
    output.mkdir()
    site.mkdir()
    monkeypatch.setattr(build, "OUTPUT", output)
    monkeypatch.setattr(build, "SITE_DATA", site)
    repos = [
        {"full_name": "o/tool", "org": "o", "name": "tool", "description": None, "is_fork": False},
        {"full_name": "o/app", "org": "o", "name": "app", "description": "x", "is_fork": False},
    ]
    content = {"workflows": {}, "n_files": 3, "file_types": {"code": 3}, "head": "abc"}
    scan = {
        "o/tool": {**content, "uses": [], "build_requires": [], "last_commit": "2026-10-01"},
        "o/app": {**content, "uses": ["o/tool@v1"], "build_requires": ["o-lib"]},  # an old scan without a date
    }
    label = {"kind": "package", "deploys_live_service": None, "security_boundary": False, "rationale": "r"}
    package = {"system": "PYPI", "name": "o-lib", "repo": "o/tool", "reason": "r", "downloads_last_month": 9}
    package |= {"dependents": 2, "latest_release": "2026-09-29"}
    for name, data in {
        "repos": {"fetched_on": "2026-10-29", "orgs": ["o"], "repos": repos},
        "scan": scan,
        "packages": {"accepted": [package], "rejected": []},
        "classification": {"o/tool": label, "o/app": label},
    }.items():
        (output / f"{name}.json").write_text(json.dumps(data))

    build.main()

    out_repos = {r["id"]: r for r in json.loads((site / "repos.json").read_text())}
    out_packages = {p["id"]: p for p in json.loads((site / "packages.json").read_text())}
    assert out_repos["o/tool"]["last_commit"] == "2026-10-01"
    assert out_repos["o/app"]["last_commit"] is None
    assert out_packages["PYPI:o-lib"]["latest_release"] == "2026-09-29"
    for repo in out_repos.values():
        related = [*repo["packages"], *(i for ids in [*repo["used_by"].values(), *repo["uses"].values()] for i in ids)]
        assert all(i in out_repos or i in out_packages for i in related)
    assert out_repos["o/tool"]["packages"] == ["PYPI:o-lib"]
    assert out_repos["o/app"]["uses"] == {"ci": ["o/tool"], "ci_pinned": [], "build": ["o/tool"]}
    assert all(p["repo"] in out_repos for p in out_packages.values())
