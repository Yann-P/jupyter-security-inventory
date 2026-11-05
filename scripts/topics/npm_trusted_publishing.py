"""Topic: was the latest version of each of the repo's npm packages published with trusted publishing?

Trusted publishing publishes from CI with a short-lived token instead of a stored one, and adds provenance.
Maintainers set it up for each package on npmjs.com.
"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic, names


def check(repo: dict, scan: dict) -> Result:
    packages = [p for p in repo["packages"] if p["system"] == "NPM"]
    if not packages:
        return Result(NOT_APPLICABLE, "No npm package.")
    without = [p for p in packages if not p["trusted_publishing"]]
    if not without:
        one = len(packages) == 1
        return Result(DONE, f"Its latest npm version{'' if one else 's'} used trusted publishing.")
    status = PARTIAL if len(without) < len(packages) else MISSING
    if len(without) == 1:
        return Result(status, f"The latest version of {names(without)} did not use trusted publishing.")
    return Result(status, f"The latest versions of {names(without)} did not use trusted publishing.")


TOPIC = Topic(
    id="npm-trusted-publishing",
    title="npm trusted publishing",
    question="Does the repository publish its npm packages with trusted publishing?",
    detection=(
        "We ask npm whether the latest version of each npm package was published with trusted publishing: from CI,"
        " with a short-lived token instead of a stored one. Maintainers set it up for each package on npmjs.com and"
        " in their release workflow, so a package gets it only from its next release on."
    ),
    meanings={
        DONE: "The latest version of each of its npm packages used trusted publishing.",
        PARTIAL: "Some of its npm packages used trusted publishing for their latest version, and some didn't.",
        MISSING: "None of its npm packages used trusted publishing for its latest version.",
        NOT_APPLICABLE: "It has no npm package.",
    },
    check=check,
)
