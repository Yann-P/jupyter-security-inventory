"""Topic: does the repo check its GitHub workflows with zizmor?

zizmor is a static analyzer for GitHub Actions workflows. A repo can run it as its GitHub Action, as a command in a
workflow (`uvx zizmor .`), or as a pre-commit hook. A hook only protects pull requests if CI runs pre-commit, for
example through pre-commit.ci, which we cannot see from the repo, so a hook with no sign of CI is only partial.
"""

from topics import DONE, MISSING, NOT_APPLICABLE, PARTIAL, Result, Topic

PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"


def check(scan: dict) -> Result:
    in_workflows = scan["mentions"].get("zizmor", [])
    action = scan["mentions"].get("zizmor-action", [])
    pre_commit = scan["pre_commit"]
    hook = pre_commit is not None and any("zizmor" in name for name in pre_commit["repos"] + pre_commit["hooks"])
    ci_runs_pre_commit = scan["mentions"].get("pre-commit", [])
    configs = [path for path in scan["config_files"] if "zizmor" in path]

    via = []
    if action:
        via.append("GitHub Action")
    if set(in_workflows) - set(action):
        via.append("workflow command")
    if hook:
        via.append("pre-commit")
    evidence = set(in_workflows) | set(configs) | ({PRE_COMMIT_CONFIG} if hook else set())

    if in_workflows:
        return Result(DONE, "Runs in a workflow.", via, sorted(evidence))
    if hook and ci_runs_pre_commit:
        return Result(
            DONE, "Pre-commit hook, and a workflow runs pre-commit.", via, sorted(evidence | set(ci_runs_pre_commit))
        )
    if hook and pre_commit["ci"]:
        return Result(DONE, "Pre-commit hook, run by pre-commit.ci.", via, sorted(evidence))
    if hook:
        return Result(PARTIAL, "Pre-commit hook, but nothing shows that CI runs pre-commit.", via, sorted(evidence))
    if configs:
        return Result(PARTIAL, "Has a zizmor config file, but nothing runs zizmor.", via, sorted(evidence))
    if scan["workflows"]["count"]:
        return Result(MISSING, "No sign of zizmor.")
    return Result(NOT_APPLICABLE, "No GitHub workflows.")


TOPIC = Topic(
    id="zizmor",
    title="zizmor",
    question="Does the repository check its GitHub workflows with zizmor?",
    applies_to="Repositories with GitHub workflows",
    detection=(
        "We look for zizmor in the repository's workflows and action files (its GitHub Action or a command), in its"
        ' pre-commit hooks, and for a zizmor config file. Comments are ignored, so a note like "zizmor: ignore" does'
        " not count. A pre-commit hook counts as running in CI when a workflow runs pre-commit or the pre-commit config"
        ' has a "ci" section, which sets up pre-commit.ci.'
    ),
    meanings={
        DONE: "zizmor runs in CI.",
        PARTIAL: "zizmor is set up, but nothing shows that CI runs it.",
        MISSING: "The repository has workflows and no sign of zizmor.",
        NOT_APPLICABLE: "The repository has no GitHub workflows to check.",
    },
    check=check,
)
