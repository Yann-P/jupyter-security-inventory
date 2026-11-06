"""Topic: do the repo's PyPI packages require a Python that still gets security fixes?

On an end-of-life Python, users also get old releases of every dependency that has dropped it.
"""

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic, names

# From https://peps.python.org/api/release-cycle.json. A month alone means its first day.
END_OF_LIFE = {
    "2.6": "2013-10-29",
    "2.7": "2020-01-01",
    "3.0": "2009-06-27",
    "3.1": "2012-04-09",
    "3.2": "2016-02-20",
    "3.3": "2017-09-29",
    "3.4": "2019-03-18",
    "3.5": "2020-09-30",
    "3.6": "2021-12-23",
    "3.7": "2023-06-27",
    "3.8": "2024-10-07",
    "3.9": "2025-10-31",
    "3.10": "2026-10-01",
    "3.11": "2027-10",
    "3.12": "2028-10",
    "3.13": "2029-10",
    "3.14": "2030-10",
    "3.15": "2031-10",
    "3.16": "2032-10",
}


def oldest_python(requires_python: str | None) -> str | None:
    """ ">=3.9.2" -> "3.9". pip ignores a missing or invalid Requires-Python, so those allow every version."""
    try:
        allowed = SpecifierSet(requires_python or "")
    except InvalidSpecifier:
        allowed = SpecifierSet()
    candidates = (f"{version}.{patch}" for version in END_OF_LIFE for patch in range(50))
    first = next(allowed.filter(candidates), None)
    return first.rsplit(".", 1)[0] if first else None


def check(repo: dict, scan: dict) -> Result:
    packages = [package for package in repo["packages"] if package["system"] == "PYPI"]
    if not packages:
        return Result(NOT_APPLICABLE, "No PyPI package.")
    oldest = {package["name"]: oldest_python(package["requires_python"]) for package in packages}
    without = [
        package
        for package in packages
        if oldest[package["name"]] and END_OF_LIFE[oldest[package["name"]]] <= repo["fetched_on"]
    ]
    if not without:
        version = min(filter(None, oldest.values()), key=list(END_OF_LIFE).index, default=None)
        least = f"at least Python {version}" if version else "a Python newer than any we know"
        one = len(packages) == 1
        return Result(DONE, f"Its latest PyPI release{'' if one else 's'} require{'s' if one else ''} {least}.")
    status = PARTIAL if len(without) < len(packages) else MISSING
    if len(without) > 1:
        reason = f"The latest releases of {names(without)} allow a Python that no longer gets security fixes."
    elif not without[0]["requires_python"]:
        reason = f"The latest release of {names(without)} sets no Requires-Python, so it installs on any Python."
    else:
        version = oldest[without[0]["name"]]
        reason = (
            f"The latest release of {names(without)} allows Python {version}, which has had no security fixes since"
            f" {END_OF_LIFE[version]}."
        )
    return Result(status, reason)


TOPIC = Topic(
    id="supported-python",
    title="Supported Python",
    question="Do the repository's PyPI packages require a Python that still gets security fixes?",
    detection=(
        "We read from PyPI the Requires-Python of the latest release of each PyPI package, the Python versions pip and"
        " uv install it on, and find the oldest one it allows. A release without Requires-Python installs on any"
        " Python. We compare with the day CPython stops shipping security fixes for that version, as listed on"
        " peps.python.org, about five years after its release. This is what the package claims: its CI may test only"
        " newer versions, and its dependencies may need a newer one."
    ),
    meanings={
        DONE: "The latest release of each of its PyPI packages requires a Python that still gets security fixes.",
        PARTIAL: "Some of its PyPI packages still allow a Python that no longer gets security fixes, and some don't.",
        MISSING: "All its PyPI packages still allow a Python that no longer gets security fixes.",
        NOT_APPLICABLE: "It has no PyPI package.",
    },
    check=check,
)
