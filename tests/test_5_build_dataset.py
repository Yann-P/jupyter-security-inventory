"""Tests for scripts/5_build_dataset.py."""

import importlib

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
