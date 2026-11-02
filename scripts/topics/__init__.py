"""Security topics: each asks one question about every repo and answers it from the facts step 2 recorded.

A topic is a module of this package with a TOPIC in it. All detection lives here: the site only shows what
output/topics.json says, and knows nothing about any particular topic. To add one, write the module and list it
in scripts/8_topics.py.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

DONE, PARTIAL, MISSING, NOT_APPLICABLE = "done", "partial", "missing", "n/a"
STATUSES = (DONE, PARTIAL, MISSING, NOT_APPLICABLE)


@dataclass
class Result:
    """What a topic found in one repo.

    `reason` is a short sentence. `via` names the ways the repo does it. `evidence` lists the files in the repo that
    show it, so that a reader can check.
    """

    status: str
    reason: str
    via: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}")


@dataclass
class Topic:
    """`check` takes a repo's entry of scan.json. `meanings` says what each status means for this topic.

    The id names the topic's page and files, so it is lower case letters, digits and hyphens.
    """

    id: str
    title: str
    question: str
    detection: str
    meanings: dict[str, str]
    check: Callable[[dict], Result]

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", self.id):
            raise ValueError(f"topic id {self.id!r}: use lower case letters, digits and hyphens")
        if set(self.meanings) != set(STATUSES):
            raise ValueError(f"topic {self.id}: meanings must cover exactly {STATUSES}")
