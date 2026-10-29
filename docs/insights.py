"""Pages and tables for the site, generated from output/ each time Sphinx starts.

conf.py calls build(), which:
- writes short CSV tables into docs/_generated/ for the hand-written pages to include,
- writes a page per organization (docs/orgs/<org>.md) and per repository (docs/orgs/<org>/<repo>.md),
- returns the numbers the hand-written pages quote, as MyST substitutions: {{ repos }}, ...

Text that comes from the repositories themselves (descriptions, labels, workflow contents) goes through
plain(), so it always shows as text and never becomes HTML, a link or a substitution.

Repositories are listed most downloaded first, then by how many other repositories run their code.
"""

import csv
import json
import re
import shutil
from collections import Counter
from functools import cached_property
from pathlib import Path
from urllib.parse import quote

DOCS = Path(__file__).parent
OUTPUT = DOCS.parent / "output"
GENERATED = DOCS / "_generated"
KINDS = ["package", "application", "tooling", "deployment", "documentation", "example", "other"]
# Table rows are tinted by kind (docs/_static/custom.css); this legend explains the colors.
LEGEND = "Rows are colored by kind: " + " ".join(f"[{kind}]{{.kind-{kind} .legend}}" for kind in KINDS)
# Listed in a second table, after the software, unless they publish a package or are a security boundary.
OUT_OF_THE_WAY = {"documentation", "example"}
REGISTRY_TOKEN = re.compile(r"PYPI|TWINE|NPM", re.I)  # secret names that hold a PyPI or npm token
# How step 3 names a registry -> its name on the site, which in lower case is also the name of its page.
REGISTRIES = {"PYPI": "PyPI", "NPM": "npm"}
# Packages and images have the same columns. Their tables are not tinted by kind, which is for repos.
PACKAGE_HEADER = ["package", "organization", "repository", "downloads/month", "dependents", "last published"]
IMAGE_HEADER = ["image", "registry", "tag", "organization", "repository", "all-time pulls", "last published"]

REPO_PAGE = """# {title}

{description}

{kind} · [on GitHub](https://github.com/{name}) · scanned at commit [{commit}](https://github.com/{name}/tree/{sha}){fork}

## Reach

- **Packages:** {packages}
- **Container images:**{images}
- **Run by other repositories:** {users}
- **Live service:** {service}
- **Security boundary:** {boundary}
- **Why these labels:** {rationale} ({model})

## CI and releases

- **Workflows:** {workflows}
- **Publishes:** {publishes}
- **Secrets:** {secrets}
- **Actions:** {actions}
- **Build requirements:** {build}

## Details

{details}
"""

ORG_PAGE = """---
html_theme.sidebar_secondary.remove: true
---

# {title}

{summary}

{body}

```{{toctree}}
:hidden:

{pages}
```
"""


def load(name: str):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def plain(text) -> str:
    """Text shown exactly as it is: Markdown can't interpret any of it once punctuation is escaped."""
    return re.sub(r"([!-/:-@\[-`{-~])", r"\\\1", str(text or "")).replace("\n", " ")


def n(number) -> str:
    return "unknown" if number is None else f"{number:,}"


def grouped(count: str) -> str:
    """A number as output/repos.csv has it, with thousands separators: '55663064' -> '55,663,064'."""
    return f"{int(count):,}" if count else ""


def slug(full_name: str) -> str:
    """The page of a repo: orgs/<org>/<repo>, with "dot" in front of names like ".github"."""
    org, name = full_name.split("/")
    return f"orgs/{org}/{'dot' + name if name.startswith('.') else name}"


def link(full_name: str) -> str:
    return f"[{plain(full_name)}](/{slug(full_name)}.md)"


def links(full_names) -> str:
    return ", ".join(link(name) for name in full_names)


def registry_url(key: str) -> str:
    """'PYPI:jupyterhub' -> the page of jupyterhub on PyPI."""
    system, name = key.split(":", 1)
    if system == "PYPI":
        return f"https://pypi.org/project/{quote(name, safe='')}/"
    return f"https://www.npmjs.com/package/{quote(name, safe='@/')}"


def package(top: str | None) -> str:
    """'PYPI:jupyterhub' -> the Python logo and a link to jupyterhub on PyPI (the npm logo for npm)."""
    if not top:
        return ""
    system, name = top.split(":", 1)
    icon = "fa-python" if system == "PYPI" else "fa-npm"  # the logo is drawn by the theme's Font Awesome
    return f"[]{{.fa-brands .{icon}}} [{plain(name)}]({registry_url(top)})"


def image_cell(ref: str | None) -> str:
    """'docker.io/jupyterhub/jupyterhub' -> the container logo and a link to the image on its registry."""
    if not ref:
        return ""
    registry, path = ref.split("/", 1)
    return f"[]{{.fa-brands .fa-docker}} [{plain(path)}]({image_url(registry, path)})"


def stats(top: str | None, count: str) -> str:
    """A download count that links to its history: pypistats.org for PyPI, npm-stat.com for npm."""
    if not top or not count:
        return count
    system, name = top.split(":", 1)
    if system == "PYPI":
        url = f"https://pypistats.org/packages/{re.sub(r'[-_.]+', '-', name).lower()}"
    else:
        url = f"https://npm-stat.com/charts.html?package={quote(name, safe='@/')}"
    return f"[{count}]({url})"


def date(day: str | None) -> str:
    """A date in a table, kept on one line: '2026-10-28' would otherwise wrap at its hyphens."""
    return f"[{day}]{{.date}}" if day else ""


def counted(number: int, one: str, many: str) -> str:
    """counted(1, "is a boundary", "are boundaries") -> '1 is a boundary'."""
    return f"{number} {one if number == 1 else many}"


def org_summary(org: str, counts: dict) -> str:
    """'github.com/jupyter has 60 public repositories: 23 publish a package, 6 are security ...'"""
    facts = [
        counted(counts["packaged"], "publishes a package", "publish a package"),
        counted(counts["boundaries"], "is a security boundary", "are security boundaries"),
        counted(counts["services"], "deploys a live service", "deploy a live service"),
    ]
    facts = [fact for fact in facts if not fact.startswith("0 ")]
    sentence = f"[github.com/{org}](https://github.com/{org}) has " + counted(
        counts["repos"], "public repository", "public repositories"
    )
    if facts:
        sentence += ": " + (", ".join(facts[:-1]) + " and " + facts[-1] if len(facts) > 1 else facts[0])
    return sentence + "."


def ref_kind(ref: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return "commit"
    return "tag" if re.match(r"v?\d", ref) else "branch"


def write_csv(path: Path, header: list[str], rows: list[list]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


class Data:
    """Everything in output/, with the few facts the pages derive from it."""

    def __init__(self):
        dataset = load("jupyter_repos.json")
        self.repos = {repo["full_name"]: repo for repo in dataset["repos"]}
        self.scan = load("scan.json")
        self.images = load("images.json")["images"]
        self.orgs = load("repos.json")["orgs"]
        with open(OUTPUT / "repos.csv", encoding="utf-8") as file:
            self.table = list(csv.DictReader(file))
        self.jupyter = {org.lower() for org in self.orgs}

    @cached_property
    def orgs_with_repos(self) -> set:
        return {repo["org"] for repo in self.repos.values()}

    def org_cell(self, org: str) -> str:
        """An organization in a table: a link to its page, which exists once it has a repository."""
        return f"[{plain(org)}](/orgs/{org}.md)" if org in self.orgs_with_repos else plain(org)

    def repo_cell(self, name: str | None) -> str:
        """A repository in a table: a link to its page, or nothing when there is none."""
        if not name:
            return ""
        return link(name) if name in self.repos else plain(name)

    def users(self, name: str) -> set:
        """The other repos that run this repo's actions or build tools without pinning them."""
        used_by = self.repos[name]["used_by"]
        return set(used_by["ci"] + used_by["build"])

    def by_reach(self, names) -> list[str]:
        """Most downloaded first, then most used in other repos' CI."""
        return sorted(
            names, key=lambda name: (-self.repos[name]["max_downloads_last_month"], -len(self.users(name)), name)
        )

    def tokens(self, name: str) -> list[str]:
        return sorted(s for s in self.repos[name]["content"]["workflows"]["secrets"] if REGISTRY_TOKEN.search(s))

    def actions(self, name: str) -> list[tuple[str, str]]:
        """The actions a repo uses, as (action, ref)."""
        return [tuple(use.split("@", 1)) for use in self.scan[name]["uses"]]

    def third_party(self, action: str) -> bool:
        """Not from Jupyter, and not from GitHub itself."""
        return action.split("/")[0].lower() not in self.jupyter | {"actions", "github"}

    def out_of_the_way(self, name: str) -> bool:
        """Documentation and examples that publish nothing and guard nothing: listed after the software."""
        return (
            self.label(name, "kind") in OUT_OF_THE_WAY
            and not self.repos[name]["top_package"]
            and not self.label(name, "security_boundary")
        )

    def cell(self, name: str) -> str:
        """A repo in a table: a link to its page, tagged with its kind so the row gets that color."""
        return f"[{link(name)}]{{.kind-{self.label(name, 'kind')}}}"

    def label(self, name: str, key: str):
        return self.repos[name]["classification"][key]

    def downloads(self, name: str) -> str:
        """Monthly downloads, or nothing for repos that publish no package."""
        repo = self.repos[name]
        return stats(repo["top_package"], n(repo["max_downloads_last_month"])) if repo["top_package"] else ""


def repo_rows(data: Data, names) -> list[list]:
    """Rows of output/repos.csv for these repos, with links and readable package names."""
    rows = {row["repo"]: row for row in data.table}
    linked = []
    for name in data.by_reach(names):
        row = rows[name]
        linked.append(
            [
                data.cell(name),
                row["kind"],
                package(row["package"]),
                stats(row["package"], grouped(row["downloads/month"])),
                grouped(row["dependents"]),
                image_cell(row["image"]),
                grouped(row["all-time pulls"]),
                grouped(row["used in CI"]),
                plain(row["live service"]),
                f"[{plain(row['security boundary'])}]{{.reason}}" if row["security boundary"] else "",
            ]
        )
    return linked


def docs_rows(data: Data, names) -> list[list]:
    """Rows for documentation and examples: the ones that deploy a site first."""
    names = sorted(names, key=lambda name: (not data.label(name, "deploys_live_service"), name))
    return [
        [data.cell(name), data.label(name, "kind"), plain(data.label(name, "deploys_live_service"))] for name in names
    ]


def published(data: Data, system: str) -> list[tuple[str, dict]]:
    """The packages of one registry as (repo, package), most downloaded first, then most depended on."""
    found = [(name, p) for name, repo in data.repos.items() for p in repo["packages"] if p["system"] == system]
    return sorted(
        found,
        key=lambda item: (-(item[1]["downloads_last_month"] or 0), -(item[1]["dependents"] or 0), item[1]["name"]),
    )


def package_row(data: Data, name: str, p: dict) -> list:
    """A row of PACKAGE_HEADER."""
    key = f"{p['system']}:{p['name']}"
    return [
        f"[{plain(p['name'])}]({registry_url(key)})",
        data.org_cell(data.repos[name]["org"]),
        data.repo_cell(name),
        stats(key, n(p["downloads_last_month"])),
        n(p["dependents"]),
        date(p["last_published"]),
    ]


def package_pages(data: Data) -> list[list]:
    """Writes a table of the published packages per registry. Returns the rows of the summary table."""
    summary = []
    for system, title in REGISTRIES.items():
        found = published(data, system)
        write_csv(
            GENERATED / f"packages-{title.lower()}.csv", PACKAGE_HEADER, [package_row(data, *item) for item in found]
        )
        top = f"{system}:{found[0][1]['name']}" if found else None
        summary.append(
            [
                f"[{title}](/packages/{title.lower()}.md)",
                len(found),
                len({name for name, _ in found}),
                len({data.repos[name]["org"] for name, _ in found}),
                package(top),
                stats(top, n(found[0][1]["downloads_last_month"])) if top else "",
            ]
        )
    return summary


def image_path(image: dict) -> str:
    return f"{image['namespace']}/{image['name']}"


def image_url(registry: str, path: str) -> str:
    """The page of an image on its registry. `path` is 'namespace/name'."""
    if registry == "docker.io":
        return f"https://hub.docker.com/r/{path}"
    return f"https://quay.io/repository/{path}"


def image_row(data: Data, image: dict) -> list:
    """A row of IMAGE_HEADER. The organization is the registry namespace."""
    path = image_path(image)
    return [
        f"[{plain(path)}]({image_url(image['registry'], path)})",
        image["registry"],
        plain(image["tag"]),
        data.org_cell(image["namespace"]),
        data.repo_cell(image["repo"]),
        n(image["pulls"]) if image["pulls"] is not None else "",
        date(image["last_published"]),
    ]


def image_rows(data: Data, images: list[dict]) -> list[list]:
    """Rows of IMAGE_HEADER, most pulled first. Quay publishes no pull counts, so its images come last."""
    ordered = sorted(images, key=lambda i: (-(i["pulls"] or 0), i["registry"], i["namespace"], i["name"]))
    return [image_row(data, image) for image in ordered]


def without_org(header: list[str], rows: list[list]) -> tuple[list[str], list[list]]:
    """A table of an organization's page leaves out the organization column: it is the same on every row."""
    at = header.index("organization")
    return header[:at] + header[at + 1 :], [row[:at] + row[at + 1 :] for row in rows]


def csv_table(file: str) -> str:
    """The Markdown for a sortable table whose rows are in <file>.csv, next to the page."""
    return f"```{{csv-table}}\n:file: {file}.csv\n:header-rows: 1\n:class: sphinx-datatable\n```"


def org_body(org: str, software: list, docs: list, packages: dict, images: list) -> str:
    """The sections of an organization's page: repositories, packages (a table per registry) and images.

    `packages` maps a registry's title to its rows. A table with no rows is left out, and so is a section with no
    table. With more than one section, a line of links to them comes first.
    """
    sections = [  # (title, note, [(subtitle, CSV file, rows)])
        ("Repositories", LEGEND, [("Software", org, software), ("Documentation and examples", f"{org}-docs", docs)]),
        (
            "Packages",
            "Downloads are for the last month and include CI.",
            [(title, f"{org}-{title.lower()}", rows) for title, rows in packages.items()],
        ),
        (
            "Images",
            "Pulls are all-time Docker Hub counts and include CI; Quay publishes none.",
            [(None, f"{org}-images", images)],
        ),
    ]
    links, parts = [], []
    for title, note, tables in sections:
        tables = [table for table in tables if table[2]]
        if tables:
            links.append(f"[{title} ({sum(len(rows) for *_, rows in tables)})](#{title.lower()})")
            blocks = [f"### {sub}\n\n{csv_table(file)}" if sub else csv_table(file) for sub, file, _ in tables]
            parts.append(f"## {title}\n\n{note}\n\n" + "\n\n".join(blocks))
    return "\n\n".join(([" · ".join(links)] if len(links) > 1 else []) + parts)


def image_item(image: dict) -> str:
    """An image on its repo's page: where to find it, how often it was pulled and when it was last published."""
    pulls = f", {n(image['pulls'])} pulls" if image["pulls"] is not None else ""
    path = image_path(image)
    return f"[{plain(path)}]({image_url(image['registry'], path)}) on {image['registry']}{pulls}, last published {image['last_published']}"


def repo_page(data: Data, name: str) -> str:
    repo, used_by = data.repos[name], data.repos[name]["used_by"]
    users = [
        f"{len(used_by[key])} {what}"
        for key, what in (("ci", "in their CI"), ("build", "in their builds"), ("ci_pinned", "pinned to a commit"))
        if used_by[key]
    ]

    actions = data.actions(name)
    kinds = Counter(ref_kind(ref) for _, ref in actions)
    risky = [
        f"{plain(action)}\\@{plain(ref)}"
        for action, ref in actions
        if data.third_party(action) and ref_kind(ref) != "commit"
    ]
    summary = ", ".join(f"{kinds[kind]} by {kind}" for kind in ("commit", "tag", "branch") if kinds[kind])
    if set(kinds) == {"commit"}:
        summary = "all pinned to a commit"
    if risky:
        summary += ". Third-party, not pinned: " + ", ".join(risky)

    details = []
    for key, what in (
        ("ci", "Run it in their CI"),
        ("build", "Run it in their builds"),
        ("ci_pinned", "Run it pinned to a commit"),
    ):
        if used_by[key]:
            details.append(f"- **{what}:** {links(used_by[key])}")
    if actions:
        uses = [
            f"{link(action) if action in data.repos else plain(action)}\\@{plain(ref[:7] if ref_kind(ref) == 'commit' else ref)}"
            for action, ref in actions
        ]
        details.append("- **All actions it uses:** " + ", ".join(uses))
    file_types = Counter(repo["content"]["file_types"]).most_common()
    details.append(
        f"- **Files:** {n(repo['content']['n_files'])}: "
        + ", ".join(f"{n(count)} {kind}" for kind, count in file_types)
    )

    workflows = repo["content"]["workflows"]
    return REPO_PAGE.format(
        title=plain(name),
        name=name,
        description=plain(repo["description"]),
        kind=data.label(name, "kind"),
        commit=repo["content"]["commit"][:7],
        sha=repo["content"]["commit"],
        fork=" · fork" if repo["is_fork"] else "",
        packages="; ".join(
            f"{package(p['system'] + ':' + p['name'])}, {stats(p['system'] + ':' + p['name'], n(p['downloads_last_month']))} downloads/month,"
            f" {n(p['dependents'])} dependents, last published {p['last_published'] or 'unknown'}"
            for p in repo["packages"]
        )
        or "none",
        images="".join(f"\n  - {image_item(image)}" for image in repo["images"]) or " none",
        users=", ".join(users) or "none",
        service=plain(data.label(name, "deploys_live_service")) or "none",
        boundary=f"yes, it {plain(data.label(name, 'security_boundary'))}"
        if data.label(name, "security_boundary")
        else "no",
        rationale=plain(data.label(name, "rationale")),
        model=plain(data.label(name, "model")),
        workflows=f"{workflows['count']}, run on " + ", ".join(map(plain, workflows["triggers"]))
        if workflows["count"]
        else "none",
        publishes=", ".join(map(plain, workflows["publishes"])) or "nothing",
        secrets=", ".join(map(plain, workflows["secrets"])) or "none",
        actions=f"{len(actions)}, {summary}" if actions else "none",
        build=", ".join(map(plain, data.scan[name]["build_requires"])) or "none",
        details="\n".join(details),
    )


def org_pages(data: Data) -> list[list]:
    """A page per organization, with a page per repository under it. Returns the rows of the summary table."""
    shutil.rmtree(DOCS / "orgs", ignore_errors=True)  # generated: pages of repos that are gone must go too
    summary = {}  # organization -> its row in the summary table
    top_downloads = {}  # organization -> downloads of its most installed package, to sort by
    for org in data.orgs:
        names = data.by_reach(name for name in data.repos if data.repos[name]["org"] == org)
        org_images = [image for image in data.images if image["namespace"] == org]
        if not names:  # no public, non-archived repositories
            summary[org] = [plain(org), 0, 0, len(org_images), 0, 0, 0, "", ""]
            continue
        software = repo_rows(data, [name for name in names if not data.out_of_the_way(name)])
        docs = docs_rows(data, [name for name in names if data.out_of_the_way(name)])
        write_csv(DOCS / "orgs" / f"{org}.csv", list(data.table[0]), software)
        write_csv(DOCS / "orgs" / f"{org}-docs.csv", ["repo", "kind", "live service"], docs)
        packages = {}
        for system, title in REGISTRIES.items():
            found = [(name, p) for name, p in published(data, system) if data.repos[name]["org"] == org]
            header, rows = without_org(PACKAGE_HEADER, [package_row(data, *item) for item in found])
            write_csv(DOCS / "orgs" / f"{org}-{title.lower()}.csv", header, rows)
            packages[title] = rows
        header, image_table = without_org(IMAGE_HEADER, image_rows(data, org_images))
        write_csv(DOCS / "orgs" / f"{org}-images.csv", header, image_table)
        (DOCS / "orgs" / org).mkdir()
        for name in names:
            (DOCS / f"{slug(name)}.md").write_text(repo_page(data, name), encoding="utf-8")
        counts = {
            "repos": len(names),
            "packaged": sum(bool(data.repos[name]["top_package"]) for name in names),
            "boundaries": sum(bool(data.label(name, "security_boundary")) for name in names),
            "services": sum(bool(data.label(name, "deploys_live_service")) for name in names),
            "tokens": sum(bool(data.tokens(name)) for name in names),
        }
        pages = "\n".join(slug(name).removeprefix("orgs/") for name in names)
        page = ORG_PAGE.format(
            title=plain(org),
            summary=org_summary(org, counts),
            pages=pages,
            body=org_body(org, software, docs, packages, image_table),
        )
        (DOCS / "orgs" / f"{org}.md").write_text(page, encoding="utf-8")
        top = data.repos[names[0]]
        top_downloads[org] = top["max_downloads_last_month"]
        summary[org] = [
            f"[{plain(org)}](/orgs/{org}.md)",
            counts["repos"],
            counts["packaged"],
            len(org_images),
            counts["boundaries"],
            counts["services"],
            counts["tokens"],
            package(top["top_package"]),
            data.downloads(names[0]),
        ]
    # By their most installed package, then by size. The sidebar lists them in the same order.
    order = sorted(summary, key=lambda org: (-top_downloads.get(org, 0), -summary[org][1]))
    pages = "\n".join(f"orgs/{org}" for org in order if summary[org][1])
    (GENERATED / "orgs-toctree.md").write_text(f"```{{toctree}}\n:hidden:\n\n{pages}\n```\n", encoding="utf-8")
    return [summary[org] for org in order]


def build() -> dict:
    shutil.rmtree(GENERATED, ignore_errors=True)
    GENERATED.mkdir()
    data = Data()
    names = list(data.repos)

    # Organizations, with a page per organization and repository
    write_csv(
        GENERATED / "orgs.csv",
        [
            "organization",
            "repos",
            "publish a package",
            "container images",
            "security boundaries",
            "live services",
            "long-lived tokens",
            "most installed package",
            "downloads/month",
        ],
        org_pages(data),
    )

    # Published packages: a table per registry
    write_csv(
        GENERATED / "packages.csv",
        ["registry", "packages", "repositories", "organizations", "most downloaded", "downloads/month"],
        package_pages(data),
    )

    # Container images
    write_csv(GENERATED / "images.csv", IMAGE_HEADER, image_rows(data, data.images))

    # All repositories: the home page
    software = [name for name in names if not data.out_of_the_way(name)]
    docs = [name for name in names if data.out_of_the_way(name)]
    write_csv(GENERATED / "repos.csv", list(data.table[0]), repo_rows(data, software))
    write_csv(GENERATED / "repos-docs.csv", ["repo", "kind", "live service"], docs_rows(data, docs))

    kinds = Counter(data.label(name, "kind") for name in names).most_common()
    return {
        "kinds": ", ".join(f"{kind} {count}" for kind, count in kinds),
        "legend": LEGEND,
        "software": n(len(software)),
        "docs": n(len(docs)),
    }
