"""Tests for scripts/8_topics.py."""

import importlib

import common
from topics import zizmor

topics = importlib.import_module("8_topics")


def test_every_topic_answers_every_repo_of_the_committed_scan():
    """So that a topic reading a fact step 2 does not keep fails here, and not in the daily update."""
    scan = common.load_json(common.OUTPUT / "scan.json")
    repos = {repo["full_name"]: repo for repo in common.load_json(common.OUTPUT / "jupyter_repos.json")["repos"]}
    assert len(topics.answer(repos, scan)) == len(topics.TOPICS) * len(scan)
    assert len({topic.id for topic in topics.TOPICS}) == len(topics.TOPICS)


def test_a_rerun_on_the_same_day_replaces_that_days_numbers_and_a_new_day_adds_a_line(tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "OUTPUT", tmp_path)
    monkeypatch.setattr(topics, "HISTORY", tmp_path / "topics_history.json")
    monkeypatch.setattr(topics, "TOPICS", [zizmor.TOPIC])
    repo = {"workflows": {"count": 1}, "mentions": {}}
    for day, scan in (("2026-11-01", {"a": repo}), ("2026-11-01", {"a": repo, "b": repo}), ("2026-11-02", {"a": repo})):
        common.save_json(tmp_path / "scan.json", scan)
        common.save_json(
            tmp_path / "jupyter_repos.json", {"fetched_on": day, "repos": [{"full_name": n} for n in scan]}
        )
        topics.main()
    history = common.load_json(tmp_path / "topics_history.json")
    assert {day: counts["zizmor"]["missing"] for day, counts in history.items()} == {"2026-11-01": 2, "2026-11-02": 1}
    assert len(common.load_json(tmp_path / "topics.json")["results"]) == 1
