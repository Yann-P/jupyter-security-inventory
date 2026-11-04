"""Topic: does the latest release of each of the repo's PyPI packages have attestations?

An attestation is made in CI with trusted publishing and names the repo and workflow that published a file.
"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic

SINCE = "2024-10-29"  # when pypa/gh-action-pypi-publish started making attestations by default


def check(repo: dict, scan: dict) -> Result:
    packages = [p for p in repo["packages"] if p["system"] == "PYPI"]
    # Only a new release can add attestations. An unknown date counts as recent.
    recent = [p for p in packages if (p["latest_published"] or SINCE) >= SINCE]
    if not recent:
        return Result(NOT_APPLICABLE, f"No PyPI release since {SINCE}." if packages else "No PyPI package.")
    without = [p["name"] for p in recent if not p["attested"]]
    if not without:
        return Result(DONE, f"Every PyPI package released since {SINCE} has attestations.")
    status = PARTIAL if len(without) < len(recent) else MISSING
    more = f" and {len(without) - 3} more" if len(without) > 3 else ""
    return Result(status, f"No attestations on the latest release of {', '.join(without[:3])}{more}.")


TOPIC = Topic(
    id="pypi-attestations",
    title="PyPI attestations",
    question="Do the repository's PyPI releases have attestations?",
    detection=(
        "We ask PyPI whether every file of the latest release of each PyPI package has an attestation. An attestation"
        " is made in CI with trusted publishing and names the repository and workflow that published the file."
        f" Packages whose latest release is older than {SINCE}, when attestations became the default, are left out."
        " PyPI's API shows trusted publishing only through attestations, so a release without them may still have"
        " used it."
    ),
    meanings={
        DONE: f"The latest release of each of its PyPI packages released since {SINCE} has attestations.",
        PARTIAL: "Some of its PyPI packages have attestations on their latest release, and some don't.",
        MISSING: "None of its PyPI packages has attestations on its latest release.",
        NOT_APPLICABLE: f"It has no PyPI package released since {SINCE}.",
    },
    check=check,
)
