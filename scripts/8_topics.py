"""Step 8: answer every security topic for every repo.

Each topic in scripts/topics/ reads a repo's facts from scan.json and jupyter_repos.json. The answers are one row per
repo and topic, so a new topic adds rows, not columns. It also keeps the number of repos per topic and status for each
day, to show progress.

Usage: python scripts/8_topics.py    Output: output/topics.json, output/topics_history.json
"""

import json
from collections import Counter
from dataclasses import asdict

from common import OUTPUT, load_json, save_json
from topics import STATUSES, npm_trusted_publishing, pypi_attestations, security_policy, supported_python, zizmor

TOPICS = [
    zizmor.TOPIC,
    security_policy.TOPIC,
    pypi_attestations.TOPIC,
    npm_trusted_publishing.TOPIC,
    supported_python.TOPIC,
]
HISTORY = OUTPUT / "topics_history.json"


def answer(repos: dict, scan: dict, day: str) -> list[dict]:
    return [
        {"topic": topic.id, "repo": name, **asdict(topic.check(repos[name] | {"fetched_on": day}, scan))}
        for topic in TOPICS
        for name in sorted(scan)
    ]


def counts(rows: list[dict]) -> dict:
    found = {topic.id: Counter(row["status"] for row in rows if row["topic"] == topic.id) for topic in TOPICS}
    return {topic: {status: tally[status] for status in STATUSES} for topic, tally in found.items()}


def save_topics(topics: list[dict], rows: list[dict]):
    """Writes topics.json with a row per line: indented, each row would take eight lines of every diff."""
    head = json.dumps(topics, indent=2, ensure_ascii=False).replace("\n", "\n  ")
    lines = ",\n".join("    " + json.dumps(row, ensure_ascii=False) for row in rows)
    (OUTPUT / "topics.json").write_text(
        f'{{\n  "topics": {head},\n  "results": [\n{lines}\n  ]\n}}\n', encoding="utf-8"
    )


def main():
    scan = load_json(OUTPUT / "scan.json")
    inventory = load_json(OUTPUT / "jupyter_repos.json")
    rows = answer({repo["full_name"]: repo for repo in inventory["repos"]}, scan, inventory["fetched_on"])
    save_topics([{key: value for key, value in asdict(topic).items() if key != "check"} for topic in TOPICS], rows)

    history = load_json(HISTORY) if HISTORY.exists() else {}
    history[inventory["fetched_on"]] = counts(rows)  # a rerun on the same day replaces it
    save_json(HISTORY, dict(sorted(history.items())))
    print(f"answered {len(TOPICS)} topics for {len(scan)} repos")


if __name__ == "__main__":
    main()
