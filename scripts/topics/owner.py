"""Topic: does the repo name its owner, in the "Owner" custom property that its organization sets on each repo?"""

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
    question="Does the repository name who owns it?",
    detection='We read the "Owner" custom property that the organization sets on each repository.',
    meanings={
        DONE: "Its Owner custom property names an owner.",
        PARTIAL: "Not used: a repository names an owner or it doesn't.",
        MISSING: "Its Owner custom property is None, or not set.",
        NOT_APPLICABLE: "Not used: every repository needs an owner.",
    },
    check=check,
)
