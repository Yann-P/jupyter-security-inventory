"""Pages and tables for the site, generated from output/ each time Sphinx starts.

conf.py calls build(), which:
- writes CSV tables into docs/_generated/ for the pages to include, each with its plain values in downloads/,
- writes the body of the home page (docs/_generated/home.md), which has the sections of an organization page,
- writes a page per organization (docs/orgs/<org>.md) and per repository (docs/orgs/<org>/<repo>.md),
- returns the notes that the hand-written pages quote, as MyST substitutions: {{ downloads_note }}, ...

Text that comes from the repositories themselves (descriptions, labels, workflow contents) goes through
plain(), so it always shows as text and never becomes HTML, a link or a substitution.

Repositories are listed most downloaded first, then by how many other repositories run their code.
"""

import csv
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
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
# These tables are not tinted by kind: that is for repo tables.
PACKAGE_HEADER = ["package", "organization", "repository", "downloads/month", "dependents", "last published"]
IMAGE_HEADER = ["image", "registry", "tag", "organization", "repository", "all-time pulls", "last published"]
DOWNLOADS_NOTE = "Downloads are for the last month and include CI."
IMAGES_NOTE = (
    "Only Docker Hub has pull counts; they are all-time and include CI."
    " The tag is `latest`, or the newest tag if there is no `latest`."
)

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


def org_link(org: str) -> str:
    return f"[{plain(org)}](/orgs/{org}.md)"


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
    return f"[]{{.fa-brands .fa-docker}} {image_link(registry, path)}"


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


def summary_sentence(subject: str, counts: dict) -> str:
    """'github.com/jupyter has 60 public repositories: 23 publish a package, 6 are security ...'"""
    facts = [
        counted(counts["packaged"], "publishes a package", "publish a package"),
        counted(counts["boundaries"], "is a security boundary", "are security boundaries"),
        counted(counts["services"], "deploys a live service", "deploy a live service"),
    ]
    facts = [fact for fact in facts if not fact.startswith("0 ")]
    sentence = f"{subject} has " + counted(counts["repos"], "public repository", "public repositories")
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


@dataclass
class Table:
    """A table of the site. `rows` are its values, which the CSV download has; `cells` are the Markdown the page shows."""

    header: list[str]
    rows: list[list]
    cells: list[list]

    def __len__(self):
        return len(self.rows)

    def without_org(self) -> Table:
        """The table without its organization column, which is the same on every row of an organization's page."""
        at = self.header.index("organization")

        def drop(row):
            return row[:at] + row[at + 1 :]

        return Table(drop(self.header), [drop(row) for row in self.rows], [drop(row) for row in self.cells])

    def write(self, stem: str):
        """Writes <stem>.csv, which a page includes, and downloads/<stem>.csv."""
        write_csv(GENERATED / f"{stem}.csv", self.header, self.cells)
        write_csv(GENERATED / "downloads" / f"{stem}.csv", self.header, self.rows)


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


def repo_table(data: Data, names) -> Table:
    """The rows of output/repos.csv for these repos, most reached first."""
    by_repo = {row["repo"]: row for row in data.table}
    csv_rows = [by_repo[name] for name in data.by_reach(names)]
    return Table(
        list(data.table[0]), [list(row.values()) for row in csv_rows], [repo_cells(data, row) for row in csv_rows]
    )


def repo_cells(data: Data, row: dict) -> list:
    """A row of output/repos.csv with links and readable package names."""
    return [
        data.cell(row["repo"]),
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


def docs_table(data: Data, names) -> Table:
    """Documentation and examples: the ones that deploy a site first."""
    names = sorted(names, key=lambda name: (not data.label(name, "deploys_live_service"), name))
    rows = [[name, data.label(name, "kind"), data.label(name, "deploys_live_service")] for name in names]
    cells = [[data.cell(name), kind, plain(service)] for name, kind, service in rows]
    return Table(["repo", "kind", "live service"], rows, cells)


def published(data: Data, system: str) -> list[tuple[str, dict]]:
    """The packages of one registry as (repo, package), most downloaded first, then most depended on."""
    found = [(name, p) for name, repo in data.repos.items() for p in repo["packages"] if p["system"] == system]
    return sorted(
        found,
        key=lambda item: (-(item[1]["downloads_last_month"] or 0), -(item[1]["dependents"] or 0), item[1]["name"]),
    )


def package_table(data: Data, system: str, names) -> Table:
    """The packages of one registry that these repos publish."""
    found = [(name, p) for name, p in published(data, system) if name in names]
    rows = [
        [p["name"], data.repos[name]["org"], name, p["downloads_last_month"], p["dependents"], p["last_published"]]
        for name, p in found
    ]
    return Table(PACKAGE_HEADER, rows, [package_cells(system, row) for row in rows])


def package_cells(system: str, row: list) -> list:
    """A row of a package table with links to the package, its organization and its repo."""
    name, org, repo, downloads, dependents, last_published = row
    key = f"{system}:{name}"
    return [
        f"[{plain(name)}]({registry_url(key)})",
        org_link(org),
        link(repo),
        stats(key, n(downloads)),
        n(dependents),
        date(last_published),
    ]


def package_summary(data: Data) -> Table:
    """The table of the registries, which link to their pages."""
    rows, cells = [], []
    for system, title in REGISTRIES.items():
        found = published(data, system)
        counts = [len(found), len({name for name, _ in found}), len({data.repos[name]["org"] for name, _ in found})]
        top = f"{system}:{found[0][1]['name']}" if found else ""
        downloads = found[0][1]["downloads_last_month"] if found else ""
        rows.append([title, *counts, top, downloads])
        cells.append(
            [f"[{title}](/packages/{title.lower()}.md)", *counts, package(top), stats(top, n(downloads)) if top else ""]
        )
    header = ["registry", "packages", "repositories", "organizations", "most downloaded", "downloads/month"]
    return Table(header, rows, cells)


def image_path(image: dict) -> str:
    return f"{image['namespace']}/{image['name']}"


def image_link(registry: str, path: str) -> str:
    """A link to an image on its registry. `path` is 'namespace/name'."""
    url = f"https://hub.docker.com/r/{path}" if registry == "docker.io" else f"https://quay.io/repository/{path}"
    return f"[{plain(path)}]({url})"


def image_table(images: list[dict]) -> Table:
    """The images, most pulled first. Quay publishes no pull counts, so its images come last."""
    ordered = sorted(images, key=lambda i: (-(i["pulls"] or 0), i["registry"], i["namespace"], i["name"]))
    rows = [
        [image_path(i), i["registry"], i["tag"], i["namespace"], i["repo"], i["pulls"], i["last_published"]]
        for i in ordered
    ]
    return Table(IMAGE_HEADER, rows, [image_cells(row) for row in rows])


def image_cells(row: list) -> list:
    """A row of the image table with links to the image, its organization (the registry namespace) and its repo."""
    path, registry, tag, org, repo, pulls, last_published = row
    return [
        image_link(registry, path),
        registry,
        plain(tag),
        org_link(org),
        link(repo) if repo else "",
        n(pulls) if pulls is not None else "",
        date(last_published),
    ]


def csv_table(stem: str, by_org: bool) -> str:
    """The Markdown for a sortable table whose rows are in <stem>.csv, with a link to download them.

    `by_org`: the table has an organization column, which gets a filter.
    """
    classes = "sphinx-datatable" + (" filter-by-org" if by_org else "")
    return (
        f"{{download}}`Download CSV </_generated/downloads/{stem}.csv>`\n\n"
        f"```{{csv-table}}\n:file: /_generated/{stem}.csv\n:header-rows: 1\n:class: {classes}\n```"
    )


def sections(scope: str, software: Table, docs: Table, packages: dict, images: Table, by_org: bool) -> str:
    """The sections of a page: repositories, packages (a table per registry) and images.

    `packages` maps a registry's title to its table. A table with no rows is left out, and so is a section with no
    table. With more than one section, a line of links to them comes first. `by_org`: the package and image tables
    have an organization column.
    """
    groups = [  # (title, note, whether its tables are filtered by organization, [(subtitle, table stem, table)])
        (
            "Repositories",
            LEGEND,
            False,
            [("Software", f"{scope}-repos", software), ("Documentation and examples", f"{scope}-docs", docs)],
        ),
        (
            "Packages",
            DOWNLOADS_NOTE,
            by_org,
            [(title, f"{scope}-{title.lower()}", table) for title, table in packages.items()],
        ),
        ("Images", IMAGES_NOTE, by_org, [(None, f"{scope}-images", images)]),
    ]
    links, parts = [], []
    for title, note, filtered, tables in groups:
        tables = [(subtitle, stem, table) for subtitle, stem, table in tables if len(table)]
        if tables:
            links.append(f"[{title} ({sum(len(table) for _, _, table in tables)})](#{title.lower()})")
            blocks = [
                f"### {subtitle}\n\n{csv_table(stem, filtered)}" if subtitle else csv_table(stem, filtered)
                for subtitle, stem, _ in tables
            ]
            parts.append(f"## {title}\n\n{note}\n\n" + "\n\n".join(blocks))
    return "\n\n".join(([" · ".join(links)] if len(links) > 1 else []) + parts)


def write_tables(data: Data, scope: str, names: list[str], images: list[dict], by_org: bool) -> str:
    """Writes the tables of a page that lists repositories, their packages and images. Returns its sections.

    `names` are the repositories of the page. Without `by_org`, the tables of packages and images
    leave out the organization column, which is the same on every row of an organization's page.
    """
    software = repo_table(data, [name for name in names if not data.out_of_the_way(name)])
    docs = docs_table(data, [name for name in names if data.out_of_the_way(name)])
    packages = {title: package_table(data, system, names) for system, title in REGISTRIES.items()}
    images = image_table(images)
    if not by_org:
        packages = {title: table.without_org() for title, table in packages.items()}
        images = images.without_org()

    software.write(f"{scope}-repos")
    docs.write(f"{scope}-docs")
    for title, table in packages.items():
        table.write(f"{scope}-{title.lower()}")
    images.write(f"{scope}-images")
    return sections(scope, software, docs, packages, images, by_org)


def image_item(image: dict) -> str:
    """An image on its repo's page: where to find it, how often it was pulled and when it was last published."""
    pulls = f", {n(image['pulls'])} pulls" if image["pulls"] is not None else ""
    path = image_path(image)
    return (
        f"{image_link(image['registry'], path)} on {image['registry']}{pulls}, last published {image['last_published']}"
    )


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


def tally(data: Data, names) -> dict:
    """What the summary sentence and the table of organizations count among these repos."""
    return {
        "repos": len(names),
        "packaged": sum(bool(data.repos[name]["top_package"]) for name in names),
        "boundaries": sum(bool(data.label(name, "security_boundary")) for name in names),
        "services": sum(bool(data.label(name, "deploys_live_service")) for name in names),
        "tokens": sum(bool(data.tokens(name)) for name in names),
    }


def org_pages(data: Data) -> Table:
    """A page per organization, with a page per repository under it. Returns the table of organizations."""
    shutil.rmtree(DOCS / "orgs", ignore_errors=True)  # generated: pages of repos that are gone must go too
    rows, cells = {}, {}  # organization -> its row in the table of organizations, as values and as the page shows it
    top_downloads = {}  # organization -> downloads of its most installed package, to sort by
    for org in data.orgs:
        names = data.by_reach(name for name in data.repos if data.repos[name]["org"] == org)
        org_images = [image for image in data.images if image["namespace"] == org]
        if not names:  # no public, non-archived repositories
            rows[org] = [org, 0, 0, len(org_images), 0, 0, 0, "", ""]
            cells[org] = [plain(org), *rows[org][1:]]
            continue
        body = write_tables(data, org, names, org_images, by_org=False)
        (DOCS / "orgs" / org).mkdir(parents=True)
        for name in names:
            (DOCS / f"{slug(name)}.md").write_text(repo_page(data, name), encoding="utf-8")
        counts = tally(data, names)
        pages = "\n".join(slug(name).removeprefix("orgs/") for name in names)
        page = ORG_PAGE.format(
            title=plain(org),
            summary=summary_sentence(f"[github.com/{org}](https://github.com/{org})", counts),
            pages=pages,
            body=body,
        )
        (DOCS / "orgs" / f"{org}.md").write_text(page, encoding="utf-8")
        top = data.repos[names[0]]
        top_downloads[org] = top["max_downloads_last_month"]
        rows[org] = [
            org,
            counts["repos"],
            counts["packaged"],
            len(org_images),
            counts["boundaries"],
            counts["services"],
            counts["tokens"],
            top["top_package"],
            top["max_downloads_last_month"] if top["top_package"] else "",
        ]
        cells[org] = [org_link(org), *rows[org][1:7], package(top["top_package"]), data.downloads(names[0])]
    # By their most installed package, then by size. The sidebar lists them in the same order.
    order = sorted(rows, key=lambda org: (-top_downloads.get(org, 0), -rows[org][1]))
    pages = "\n".join(f"orgs/{org}" for org in order if rows[org][1])
    (GENERATED / "orgs-toctree.md").write_text(f"```{{toctree}}\n:hidden:\n\n{pages}\n```\n", encoding="utf-8")
    header = [
        "organization",
        "repos",
        "publish a package",
        "container images",
        "security boundaries",
        "live services",
        "long-lived tokens",
        "most installed package",
        "downloads/month",
    ]
    return Table(header, [rows[org] for org in order], [cells[org] for org in order])


def build() -> dict:
    shutil.rmtree(GENERATED, ignore_errors=True)
    GENERATED.mkdir()
    data = Data()
    names = list(data.repos)

    # Organizations, with a page per organization and repository
    org_pages(data).write("orgs")

    # All organizations: the home page, whose package and image tables the pages of packages and images show too
    body = write_tables(data, "all", names, data.images, by_org=True)
    (GENERATED / "home.md").write_text(
        summary_sentence("Project Jupyter", tally(data, names)) + "\n\n" + body, encoding="utf-8"
    )

    # Published packages: a summary of the registries
    package_summary(data).write("packages")

    return {"downloads_note": DOWNLOADS_NOTE, "images_note": IMAGES_NOTE}
