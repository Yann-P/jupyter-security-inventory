"""Tests for scripts/1_inventory.py."""

import importlib
import json
from types import SimpleNamespace

inventory = importlib.import_module("1_inventory")  # names starting with a digit can't be imported with `import`


def test_public_repos_keeps_what_the_other_steps_need(monkeypatch):
    # What `gh repo list` and `gh api orgs/jupyter/repos --jq ...` print, so the test doesn't need GitHub.
    listing = [
        {"nameWithOwner": "jupyter/notebook", "description": "", "isFork": False, "isEmpty": False},
        {"nameWithOwner": "jupyter/new-idea", "description": "", "isFork": False, "isEmpty": True},
    ]
    owners = '["jupyter/notebook","notebook-council"]\n["jupyter/new-idea",null]\n'

    def run(command, **kwargs):
        return SimpleNamespace(stdout=json.dumps(listing) if command[1] == "repo" else owners)

    monkeypatch.setattr(inventory.subprocess, "run", run)

    assert inventory.public_repos("jupyter") == [
        {
            "full_name": "jupyter/notebook",
            "org": "jupyter",
            "name": "notebook",
            "description": None,
            "is_fork": False,
            "owner": "notebook-council",
        },
    ]
