"""Topic: does the repo have a SECURITY.md that says how to report a vulnerability?

GitHub uses the repo's own SECURITY.md, or else the one of the org's .github repo. A repo's own file is often a copy
of the org's: it only matters if it sends reports elsewhere, which we tell by its emails.
"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic


def check(repo: dict, scan: dict) -> Result:
    if not (repo["packages"] or repo["images"]):
        return Result(NOT_APPLICABLE, "Ships no package or image.")
    own = scan[repo["full_name"]]["security_policy"]
    org_repo = f"{repo['org']}/.github"
    org = scan.get(org_repo, {}).get("security_policy")
    if not own and not org:
        return Result(MISSING, f"No SECURITY.md, here or in {org_repo}.")
    if not own:
        return Result(DONE, f"Uses the SECURITY.md of {org_repo}.", ["organization"])
    if not org:
        status, reason = DONE, "Has its own SECURITY.md."
    elif own["emails"] and own["emails"] == org["emails"]:
        status, reason = DONE, f"Same emails as {org_repo}, so it is likely a copy we can remove."
    else:
        status, reason = PARTIAL, f"Not the same emails as {org_repo}: check where reports go."
    return Result(status, reason, ["repository"], [own["path"]])


TOPIC = Topic(
    id="security-policy",
    title="SECURITY.md",
    question="Does the repository say how to report a vulnerability?",
    detection=(
        "We look for a SECURITY.md where GitHub does: in the repository's .github folder, root and docs folder, then"
        " in the organization's .github repository. A repository needs one if it ships a package or a container image."
        " When the repository and its organization both have one, we compare the emails they list."
    ),
    meanings={
        DONE: "It has a SECURITY.md, its own or its organization's.",
        PARTIAL: "Its own SECURITY.md lists other emails than its organization's, so reports may go to the wrong place.",
        MISSING: "It ships a package or an image and has no SECURITY.md, not even its organization's.",
        NOT_APPLICABLE: "It ships no package or image.",
    },
    check=check,
)
