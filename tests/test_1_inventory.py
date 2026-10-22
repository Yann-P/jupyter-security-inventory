"""Tests for scripts/1_inventory.py."""

import importlib
import json
from types import SimpleNamespace

inventory = importlib.import_module("1_inventory")  # names starting with a digit can't be imported with `import`


def test_public_repos_keeps_what_the_other_steps_need(monkeypatch):
    # What `gh repo list` prints, so the test doesn't need GitHub.
    listing = [
        {"nameWithOwner": "jupyter/notebook", "description": "", "isFork": False, "isEmpty": False},
        {"nameWithOwner": "jupyter/new-idea", "description": "", "isFork": False, "isEmpty": True},
    ]
    monkeypatch.setattr(
        inventory.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(listing))
    )

    assert inventory.public_repos("jupyter") == [
        {"full_name": "jupyter/notebook", "org": "jupyter", "name": "notebook", "description": None, "is_fork": False},
    ]
