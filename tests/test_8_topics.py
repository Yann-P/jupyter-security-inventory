"""Tests for scripts/8_topics.py."""

import importlib

from topics import Result, Topic

topics = importlib.import_module("8_topics")


def make_scan(**workflows):
    """A scan.json with one repo per name, each with that many workflows."""
    return {
        name: {"workflows": {"count": count}, "mentions": {}, "pre_commit": None, "config_files": []}
        for name, count in workflows.items()
    }


def test_answer_has_a_row_per_topic_and_repo_in_a_stable_order():
    rows = topics.answer({"b/two": make_scan(x=1)["x"], "a/one": make_scan(x=0)["x"]})
    assert [(row["topic"], row["repo"], row["status"]) for row in rows] == [
        ("zizmor", "a/one", "n/a"),
        ("zizmor", "b/two", "missing"),
    ]
    assert set(rows[0]) == {"topic", "repo", "status", "reason", "via", "evidence"}


def test_counts_give_every_status_even_when_nobody_has_it(monkeypatch):
    other = Topic(
        "other",
        "Other",
        "?",
        "all",
        "",
        dict.fromkeys(("done", "partial", "missing", "n/a"), ""),
        lambda s: Result("done", ""),
    )
    monkeypatch.setattr(topics, "TOPICS", [*topics.TOPICS, other])
    rows = topics.answer(make_scan(a=1, b=1, c=0))
    assert topics.counts(rows) == {
        "zizmor": {"done": 0, "partial": 0, "missing": 2, "n/a": 1},
        "other": {"done": 3, "partial": 0, "missing": 0, "n/a": 0},
    }


def test_a_rerun_on_the_same_day_replaces_that_days_line_and_a_new_day_adds_one(tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "OUTPUT", tmp_path)
    monkeypatch.setattr(topics, "HISTORY", tmp_path / "topics_history.json")
    save = importlib.import_module("common").save_json
    save(tmp_path / "scan.json", make_scan(a=1))
    for day, scan in (
        ("2026-11-01", make_scan(a=1)),
        ("2026-11-01", make_scan(a=1, b=0)),
        ("2026-11-02", make_scan(a=1)),
    ):
        save(tmp_path / "scan.json", scan)
        save(tmp_path / "repos.json", {"fetched_on": day})
        topics.main()
    history = importlib.import_module("common").load_json(tmp_path / "topics_history.json")
    assert list(history) == ["2026-11-01", "2026-11-02"]
    assert history["2026-11-01"]["zizmor"] == {
        "done": 0,
        "partial": 0,
        "missing": 1,
        "n/a": 1,
    }  # the second run of the day
    assert history["2026-11-02"]["zizmor"] == {"done": 0, "partial": 0, "missing": 1, "n/a": 0}
    assert (tmp_path / "topics.json").exists()
