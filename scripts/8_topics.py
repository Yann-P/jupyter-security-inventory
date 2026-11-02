"""Step 8: answer every security topic for every repo.

Each topic in scripts/topics/ reads a repo's facts from scan.json and answers one question about it. The answers
are one short row per repo and topic, so a new topic adds rows and no columns.

Also keeps a count per topic and status for each day the inventory was fetched, to show progress over time.

Usage: python scripts/8_topics.py    Output: output/topics.json, output/topics_history.json
"""

from collections import Counter
from dataclasses import asdict

from common import OUTPUT, load_json, save_json
from topics import STATUSES, zizmor

TOPICS = [zizmor.TOPIC]
HISTORY = OUTPUT / "topics_history.json"


def answer(scan: dict) -> list[dict]:
    """A row per topic and repo, in the order of TOPICS and then of the repo names."""
    return [
        {"topic": topic.id, "repo": repo, **asdict(topic.check(scan[repo]))}
        for topic in TOPICS
        for repo in sorted(scan)
    ]


def counts(rows: list[dict]) -> dict:
    """{topic: {status: number of repos}}, with every status present."""
    found = {topic.id: Counter(row["status"] for row in rows if row["topic"] == topic.id) for topic in TOPICS}
    return {topic: {status: tally[status] for status in STATUSES} for topic, tally in found.items()}


def main():
    scan = load_json(OUTPUT / "scan.json")
    rows = answer(scan)
    topics = [{key: value for key, value in asdict(topic).items() if key != "check"} for topic in TOPICS]
    save_json(OUTPUT / "topics.json", {"topics": topics, "results": rows})

    history = load_json(HISTORY) if HISTORY.exists() else {}
    history[load_json(OUTPUT / "repos.json")["fetched_on"]] = counts(rows)  # a rerun on the same day replaces its line
    save_json(HISTORY, dict(sorted(history.items())))
    print(f"answered {len(TOPICS)} topics for {len(scan)} repos")


if __name__ == "__main__":
    main()
