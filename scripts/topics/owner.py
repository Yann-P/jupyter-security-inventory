"""Topic: does the repo name its owner?"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic


def check(repo: dict, scan: dict) -> Result:
    if repo["owner"] is None:
        return Result(MISSING, "It has no Owner custom property.")
    if repo["owner"] == "None":
        return Result(MISSING, "Its Owner custom property is None.")
    return Result(DONE, f"Owned by {repo['owner']}.")


TOPIC = Topic(
    id="owner",
    title="Owner",
    question="Does the repository name who owns it with the Owner custom property?",
    detection='We read the repository "Owner" custom property.',
    meanings={
        DONE: "Its Owner custom property names an owner.",
        PARTIAL: "Not used: the property cannot be partially set.",
        MISSING: "Its Owner custom property is the default value (None) or not set.",
        NOT_APPLICABLE: "Not used: the property is mandatory.",
    },
    check=check,
)
