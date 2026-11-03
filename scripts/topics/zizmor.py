"""Topic: does the repo check its GitHub workflows with zizmor?

It can run as its GitHub Action, as a command in a workflow (`uvx zizmor .`) or as a pre-commit hook. A hook only
checks pull requests if CI runs pre-commit.
"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic

PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"


def check(repo: dict, scan: dict) -> Result:
    facts = scan[repo["full_name"]]
    if not facts["workflows"]["count"]:
        return Result(NOT_APPLICABLE, "No GitHub workflows.")
    mentions = facts["mentions"]
    files = mentions.get("zizmor", [])
    workflows = [path for path in files if path != PRE_COMMIT_CONFIG]
    hook = PRE_COMMIT_CONFIG in files
    ci_runs_pre_commit = mentions.get("pre-commit", [])

    via = []
    if mentions.get("zizmor-action"):
        via.append("GitHub Action")
    if set(workflows) - set(mentions.get("zizmor-action", [])):
        via.append("workflow command")
    if hook:
        via.append("pre-commit")

    if workflows:
        return Result(DONE, "Runs in a workflow.", via, files)
    if hook and ci_runs_pre_commit:
        return Result(DONE, "Pre-commit hook, and CI runs pre-commit.", via, sorted({*files, *ci_runs_pre_commit}))
    if hook:
        return Result(PARTIAL, "Pre-commit hook, but nothing shows that CI runs pre-commit.", via, files)
    return Result(MISSING, "No sign of zizmor.")


TOPIC = Topic(
    id="zizmor",
    title="zizmor",
    question="Does the repository check its GitHub workflows with zizmor?",
    detection=(
        "We look for zizmor in the repository's workflows and action files (its GitHub Action or a command) and in its"
        ' pre-commit hooks. Comments are ignored, so a note like "zizmor: ignore" does not count. A pre-commit hook'
        ' counts as running in CI when a workflow runs pre-commit or the pre-commit config has a "ci" section, which'
        " sets up pre-commit.ci."
    ),
    meanings={
        DONE: "zizmor runs in CI.",
        PARTIAL: "zizmor is set up, but nothing shows that CI runs it.",
        MISSING: "The repository has workflows and no sign of zizmor.",
        NOT_APPLICABLE: "The repository has no GitHub workflows to check.",
    },
    check=check,
)
