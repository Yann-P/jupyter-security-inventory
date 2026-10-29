"""Step 2: clone every repo and record what it contains.

For each repo: how many files of each type, the packages its manifests declare, what its
GitHub workflows do, the GitHub Actions it uses, the container images its chartpress files build,
and the start of its README. Only those few files are downloaded; for everything else the clone
holds just the file names.

Usage: python scripts/2_scan_repos.py --clone-dir /tmp/clones    Output: output/scan.json
"""

import argparse
import json
import os
import re
import subprocess
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

import yaml
from common import OUTPUT, load_json, save_json

FILE_TYPES = {
    "code": ".py .pyx .ts .tsx .js .jsx .mjs .cjs .c .cc .cpp .h .hpp .go .rs .java .scala .kt .jl .r .lua .hs "
    ".sh .bash .ps1 .bat .cmake .rb .pl .m .swift",
    "docs": ".md .rst .txt .tex .adoc .bib",
    "notebook": ".ipynb",
    "web": ".html .htm .css .scss .less .vue .j2 .jinja .jinja2",
    "media": ".png .jpg .jpeg .gif .svg .ico .webp .pdf .mp4 .webm .mov .ttf .otf .woff .woff2 .pptx",
    "data": ".csv .tsv .parquet .h5 .hdf5 .nc .zip .gz .npy .npz .pkl .sqlite .db .xlsx .geojson",
    "config": ".yml .yaml .toml .cfg .ini .json .lock .tf .conf .in .nix",
}
TYPE_OF = {extension: kind for kind, extensions in FILE_TYPES.items() for extension in extensions.split()}

MANIFESTS = {"package.json", "pyproject.toml", "setup.py", "setup.cfg"}
CHARTPRESS = {"chartpress.yaml", "chartpress.yml"}  # chartpress builds a Helm chart's container images
# A manifest inside one of these folders is a test, an example or a vendored copy, not a published package.
NOT_PUBLISHED = {
    "node_modules",
    "test",
    "tests",
    "testing",
    "fixtures",
    "ui-tests",
    "examples",
    "example",
    "docs",
    "binder",
    "vendor",
    "third_party",
    "benchmarks",
}

# What a workflow publishes, recognized from the tools and actions it calls.
PUBLISHES = {
    "pypi": r"pypa/gh-action-pypi-publish|twine\s+upload|uv\s+publish|hatch\s+publish|flit\s+publish",
    "npm": r"npm\s+publish|yarn\s+(npm\s+)?publish|jlpm\s+publish|lerna\s+publish|NPM_TOKEN|NODE_AUTH_TOKEN",
    "jupyter_releaser": r"jupyter[-_]releaser|publish-release",
    "container": r"docker/build-push-action|docker\s+push|docker/login-action|quay\.io|ghcr\.io|chartpress\s+--push",
    "website": r"actions/deploy-pages|peaceiris/actions-gh-pages|github-pages-deploy-action|gh-pages|netlify",
    "cloud": r"kubectl\s|helm\s+upgrade|terraform\s+apply|gcloud\s|google-github-actions/auth|"
    r"aws-actions/configure-aws-credentials|azure/login|git-crypt\s+unlock|sops\s",
}
# A secret read by a workflow: "${{ secrets.PYPI_TOKEN }}"
SECRET = r"\$\{\{\s*secrets\.(\w+)"
# An action used by a workflow: "uses: org/repo@ref" or "uses: org/repo/path/to/action@ref"
USES = r"uses:\s*['\"]?([\w.-]+/[\w.-]+)(?:/[^@\s'\"]*)?@([^\s'\"#]+)"


def git(folder: Path, *args: str, stdin: str = None) -> str:
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(
        ["git", "-C", str(folder), *args], env=env, input=stdin, capture_output=True, text=True, timeout=900, check=True
    ).stdout


def clone(full_name: str, folder: Path):
    """Clone the latest commit with file names but no file contents, or move an earlier clone to it."""
    if (folder / ".git").exists():
        git(folder, "fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin", "HEAD")
        git(folder, "reset", "--quiet", "--soft", "FETCH_HEAD")  # check_out() then updates the files
        return
    folder.parent.mkdir(parents=True, exist_ok=True)
    git(
        folder.parent,
        "clone",
        "--quiet",
        "--depth",
        "1",
        "--filter=blob:none",
        "--no-checkout",
        f"https://github.com/{full_name}",
        folder.name,
    )


def check_out(folder: Path, paths: list[str]):
    """Download and check out only these files (a sparse checkout)."""
    if not paths:
        return
    # One pattern per file: "/" anchors it at the repo root, and characters git treats as wildcards are escaped.
    patterns = ["/" + re.sub(r"([*?\[\]!#\\])", r"\\\1", path) for path in paths]
    git(folder, "sparse-checkout", "set", "--no-cone", "--stdin", stdin="\n".join(patterns) + "\n")
    git(folder, "reset", "--quiet", "--hard", "HEAD")


def is_readme(path: str) -> bool:
    return "/" not in path and path.lower().startswith("readme")


def is_action(path: str) -> bool:
    return PurePosixPath(path).name in ("action.yml", "action.yaml")


def is_workflow(path: str) -> bool:
    return path.startswith(".github/workflows/") and PurePosixPath(path).suffix in (".yml", ".yaml")


def worth_reading(path: str) -> bool:
    """The README, package manifests, workflows, action definitions and chartpress files: the only files we download."""
    if "node_modules" in PurePosixPath(path).parts:
        return False
    name = PurePosixPath(path).name
    return is_readme(path) or name in MANIFESTS | CHARTPRESS or is_action(path) or is_workflow(path)


def file_type(path: str) -> str:
    return TYPE_OF.get(PurePosixPath(path).suffix.lower(), "other")


def declared_package(path: str, text: str) -> dict | None:
    """The package a manifest declares; None for private packages, templates and unreadable files."""
    filename = PurePosixPath(path).name
    system, name, private = "PYPI", None, False
    try:
        if filename == "package.json":
            data = json.loads(text)
            system, name, private = "NPM", data.get("name"), bool(data.get("private"))
        elif filename == "pyproject.toml":
            data = tomllib.loads(text)
            name = data.get("project", {}).get("name") or data.get("tool", {}).get("poetry", {}).get("name")
        elif filename == "setup.cfg":
            match = re.search(r"^name\s*=\s*([\w.-]+)\s*$", text, re.M)
            name = match.group(1) if match else None
        else:  # setup.py; name=NAME (a variable) is ignored
            match = re.search(r"\bname\s*=\s*['\"]([\w.-]+)['\"]", text)
            name = match.group(1) if match else None
    except ValueError, AttributeError, tomllib.TOMLDecodeError:
        return None
    if not name or private:
        return None
    if re.search(r"\{\{|\{%|cookiecutter", name):  # a project template, e.g. "{{ cookiecutter.name }}"
        return None
    folders = PurePosixPath(path).parts[:-1]
    return {
        "system": system,
        "name": name,
        "path": path,
        "in_test_or_example_folder": bool(set(folders) & NOT_PUBLISHED),
    }


def build_requires(pyproject: str) -> list[str]:
    """The packages needed to build a Python project: 'hatchling>=1.5' -> 'hatchling'."""
    try:
        requires = tomllib.loads(pyproject).get("build-system", {}).get("requires", [])
    except tomllib.TOMLDecodeError:
        return []
    names = []
    for requirement in requires:
        match = re.match(r"[\w.-]+", requirement)
        if match:
            names.append(match.group(0))
    return names


def chartpress_images(text: str) -> list[str]:
    """The images a chartpress file builds: for each chart, its imagePrefix and the name of each image.

    With "imagePrefix: quay.io/jupyterhub/k8s-" and an image "hub", that is "quay.io/jupyterhub/k8s-hub".
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    charts = data.get("charts") if isinstance(data, dict) else None
    names = []
    for chart in charts if isinstance(charts, list) else []:
        images = chart.get("images") if isinstance(chart, dict) else None
        for name, image in (images if isinstance(images, dict) else {}).items():
            explicit = image.get("imageName") if isinstance(image, dict) else None
            names.append(str(explicit or f"{chart.get('imagePrefix') or ''}{name}"))
    return names


def triggers(workflow: str) -> set[str]:
    """The events that start a workflow: its `on:` is a name, a list of names or a mapping keyed by name."""
    try:
        data = yaml.safe_load(workflow)
    except yaml.YAMLError:
        return set()
    if not isinstance(data, dict):
        return set()
    on = data.get("on", data.get(True))  # YAML 1.1 reads a bare `on:` key as true
    return {on} if isinstance(on, str) else {str(event) for event in on or []}


def summarize_workflows(workflows: list[str]) -> dict:
    text = "\n".join(workflows)
    return {
        "count": len(workflows),
        "triggers": sorted(set().union(*map(triggers, workflows))),
        "secrets": sorted(set(re.findall(SECRET, text)) - {"GITHUB_TOKEN"}),  # every repo has GITHUB_TOKEN
        "publishes": [kind for kind, pattern in PUBLISHES.items() if re.search(pattern, text, re.I)],
    }


def scan(full_name: str, clone_dir: Path) -> dict:
    folder = clone_dir / full_name
    clone(full_name, folder)
    paths = git(folder, "ls-tree", "-r", "--name-only", "-z", "HEAD").split("\0")[:-1]
    to_read = [path for path in paths if worth_reading(path)][:1500]  # the cap only matters for huge monorepos
    check_out(folder, to_read)

    def read(path):
        file = folder / path
        # A repo can ship a symlink to a file outside its clone (a token, an SSH key): never follow one.
        if file.is_symlink() or not file.is_file():
            return ""
        return file.read_text(encoding="utf-8", errors="replace")

    workflows = [path for path in to_read if path.startswith(".github/workflows/")]
    actions = [path for path in to_read if PurePosixPath(path).name.startswith("action.")]
    manifests = [path for path in to_read if PurePosixPath(path).name in MANIFESTS]
    chartpress = [path for path in to_read if PurePosixPath(path).name in CHARTPRESS]
    readme = next((path for path in to_read if is_readme(path)), None)

    packages, build_requirements = [], set()
    for manifest in manifests:
        package = declared_package(manifest, read(manifest))
        if package:
            packages.append(package)
        if PurePosixPath(manifest).name == "pyproject.toml":
            build_requirements.update(build_requires(read(manifest)))

    ci_text = "\n".join(read(path) for path in workflows + actions)
    return {
        "head": git(folder, "rev-parse", "HEAD").strip(),
        "n_files": len(paths),
        "file_types": dict(Counter(file_type(path) for path in paths)),
        "packages": packages,
        "workflows": summarize_workflows([read(path) for path in workflows]),
        "uses": sorted({f"{repo}@{ref}" for repo, ref in re.findall(USES, ci_text)}),
        "images": sorted({image for path in chartpress for image in chartpress_images(read(path))}),
        "build_requires": sorted(build_requirements),
        "readme": read(readme)[:2500] if readme else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clone-dir", type=Path, required=True, help="where to keep the clones")
    clone_dir = parser.parse_args().clone_dir
    names = [repo["full_name"] for repo in load_json(OUTPUT / "repos.json")["repos"]]
    with ThreadPoolExecutor(4) as pool:
        results = pool.map(lambda name: scan(name, clone_dir), names)
        save_json(OUTPUT / "scan.json", dict(zip(names, results)))
    print(f"scanned {len(names)} repos")


if __name__ == "__main__":
    main()
