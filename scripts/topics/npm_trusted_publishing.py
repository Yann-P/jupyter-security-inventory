"""Topic: was the latest version of each of the repo's npm packages published with trusted publishing?

Trusted publishing publishes from CI with a short-lived token instead of a stored one, and adds provenance.
"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic

SINCE = "2025-07-31"  # when npm trusted publishing became generally available


def check(repo: dict, scan: dict) -> Result:
    packages = [p for p in repo["packages"] if p["system"] == "NPM"]
    # Only a new release can use it. An unknown date counts as recent.
    recent = [p for p in packages if (p["latest_published"] or SINCE) >= SINCE]
    if not recent:
        return Result(NOT_APPLICABLE, f"No npm release since {SINCE}." if packages else "No npm package.")
    without = [p["name"] for p in recent if not p["trusted_publishing"]]
    if not without:
        return Result(DONE, f"Every npm package released since {SINCE} used trusted publishing.")
    status = PARTIAL if len(without) < len(recent) else MISSING
    more = f" and {len(without) - 3} more" if len(without) > 3 else ""
    return Result(status, f"No trusted publishing for the latest version of {', '.join(without[:3])}{more}.")


TOPIC = Topic(
    id="npm-trusted-publishing",
    title="npm trusted publishing",
    question="Does the repository publish its npm packages with trusted publishing?",
    detection=(
        "We ask npm whether the latest version of each npm package was published with trusted publishing: from CI,"
        f" with a short-lived token instead of a stored one. Packages whose latest version is older than {SINCE},"
        " when npm launched it, are left out."
    ),
    meanings={
        DONE: f"The latest version of each of its npm packages released since {SINCE} used trusted publishing.",
        PARTIAL: "Some of its npm packages used trusted publishing for their latest version, and some didn't.",
        MISSING: "None of its npm packages used trusted publishing for its latest version.",
        NOT_APPLICABLE: f"It has no npm package released since {SINCE}.",
    },
    check=check,
)
