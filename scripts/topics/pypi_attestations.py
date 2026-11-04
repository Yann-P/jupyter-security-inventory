"""Topic: does the latest release of each of the repo's PyPI packages have attestations?

An attestation names the repo and workflow that published a file. Maintainers set it up in their release workflow.
"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic, names


def check(repo: dict, scan: dict) -> Result:
    packages = [p for p in repo["packages"] if p["system"] == "PYPI"]
    if not packages:
        return Result(NOT_APPLICABLE, "No PyPI package.")
    without = [p for p in packages if not p["attested"]]
    if not without:
        one = len(packages) == 1
        return Result(
            DONE, "Its latest PyPI release has attestations." if one else "Its latest PyPI releases have attestations."
        )
    status = PARTIAL if len(without) < len(packages) else MISSING
    if len(without) == 1:
        return Result(status, f"The latest release of {names(without)} has no attestations.")
    return Result(status, f"The latest releases of {names(without)} have no attestations.")


TOPIC = Topic(
    id="pypi-attestations",
    title="PyPI attestations",
    question="Do the repository's PyPI releases have attestations?",
    detection=(
        "We ask PyPI whether every file of the latest release of each PyPI package has an attestation. Maintainers set"
        " this up in their release workflow: it needs trusted publishing and a tool that signs the files, which"
        " pypa/gh-action-pypi-publish does by default. Attestations are uploaded with a release, so a package gets"
        " them only from its next release on. PyPI's API shows trusted publishing only through attestations, so a"
        " release without them may still have used it."
    ),
    meanings={
        DONE: "The latest release of each of its PyPI packages has attestations.",
        PARTIAL: "Some of its PyPI packages have attestations on their latest release, and some don't.",
        MISSING: "None of its PyPI packages has attestations on its latest release.",
        NOT_APPLICABLE: "It has no PyPI package.",
    },
    check=check,
)
