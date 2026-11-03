"""Security topics: each asks one question about every repo and answers it from scan.json and jupyter_repos.json.

A topic is a module here with a TOPIC. All detection lives in these modules; the site only shows topics.json.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

DONE, PARTIAL, MISSING, NOT_APPLICABLE = "done", "partial", "missing", "n/a"
STATUSES = (DONE, PARTIAL, MISSING, NOT_APPLICABLE)


@dataclass
class Result:
    """`via` names the ways the repo does it, `evidence` the files that show it."""

    status: str
    reason: str
    via: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self):
        assert self.status in STATUSES, self.status


@dataclass
class Topic:
    """`check` takes a repo's record of jupyter_repos.json and all of scan.json, to look at other repos like the
    org's .github. The id is used in URLs and file names."""

    id: str
    title: str
    question: str
    detection: str
    meanings: dict[str, str]
    check: Callable[[dict, dict], Result]

    def __post_init__(self):
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", self.id), self.id
        assert set(self.meanings) == set(STATUSES), f"{self.id}: say what each status means"
