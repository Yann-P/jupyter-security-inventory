// The views of the site. Each one is a plain object in the `views` array below; app.js turns it into a page, a
// sortable table, a nav link and a card on the home page. To add a view, add an object. Nothing else needs to change.
//
//   id           the URL: #/view/<id>
//   title        nav link and page heading
//   description  one sentence for the home page and under the heading
//   source       which records are listed: "repos", "packages", "images" or "orgs" (orgs are derived from the repos)
//   filter       optional (record, params, ctx) => truthy to list the record
//   params       optional [{name, label, default}]: numbers shown above the table; they live in the URL
//                (#/view/stale-repos?days=90) and arrive in filter() and in accessors as params.days
//   needs        optional field that must be filled in somewhere in the data; if it is empty everywhere the page
//                shows `hint` instead of an empty table
//   columns      what to show: {title, field, type, filter, width, accessor, target, of}
//                  type      string (default) | text (long, wrapped) | number | date | list
//                            | repo | package | org (links to that page) | image (links to its registry page);
//                            `of` makes a list's items links
//                  filter    optional header filter: "text" | "select" | "min"
//                  accessor  optional (record, ctx, params) => value, for a column that is not a field of the record
//                  target    for link types: the field holding the id, if it is not `field`
//                  max       for lists: how many items to show (default 6; the repo page has them all)
//   sort         [{column: "<field>", dir: "asc" | "desc"}]
//
// Worked example, a view of the repos that nothing else depends on and that are forks:
//
//   {
//     id: "lonely-forks",
//     title: "Lonely forks",
//     description: "Forks that no other repo uses.",
//     source: "repos",
//     filter: (repo) => repo.is_fork && repo.used_in_ci === 0,
//     columns: [
//       { title: "Repository", field: "id", type: "repo", filter: "text" },
//       { title: "Description", field: "description", type: "text" },
//     ],
//     sort: [{ column: "id", dir: "asc" }],
//   },
//
// What a record looks like is in site/data/repos.json, packages.json and images.json (written by
// scripts/6_build_dataset.py).

// Columns that several views use.
const repo = { title: "Repository", field: "name", type: "repo", target: "id", filter: "text" }; // next to `org`
const org = { title: "Org", field: "org", type: "org", filter: "select" };
const kind = { title: "Kind", field: "kind", filter: "select" };
const description = { title: "Description", field: "description", type: "text" };
const downloads = { title: "Downloads / month", field: "downloads_last_month", type: "number", filter: "min" };
const packages = { title: "Packages", field: "packages", type: "list", of: "package" };
const pulls = { title: "All-time pulls", field: "pulls", type: "number", filter: "min" };
const images = { title: "Images", field: "images", type: "list", of: "image", max: 2, width: 300 }; // most pulled first
const image = { title: "Image", field: "name", type: "image", target: "id", filter: "text" }; // next to `registry`
const registry = { title: "Registry", field: "registry", filter: "select" };
const tag = { title: "Tag", field: "tag" };
const lastPublished = { title: "Last published", field: "last_published", type: "date" };
const count = (title, field, accessor) => ({ title, field, type: "number", accessor });

const MISSING_COMMIT =
  "Dates come from fetch step 2 (scripts/2_scan_repos.py); once they are in site/data/ this view fills itself.";
const MISSING_PACKAGE_DATES =
  "Dates come from fetch step 3 (scripts/3_packages.py); once they are in site/data/ this view fills itself.";
const MISSING_IMAGE_DATES =
  "Dates come from fetch step 4 (scripts/4_images.py); once they are in site/data/ this view fills itself.";

export const views = [
  {
    id: "repos",
    title: "All repos",
    description: "Every public repository of the Jupyter organizations, with what it is and what it publishes.",
    source: "repos",
    columns: [
      repo,
      org,
      kind,
      description,
      packages,
      downloads,
      images,
      pulls,
      { title: "Last commit", field: "last_commit", type: "date" },
    ],
    sort: [{ column: "name", dir: "asc" }],
  },
  {
    id: "orgs",
    title: "Organizations",
    description: "The GitHub organizations, with what each one holds. Open one to see its repos.",
    source: "orgs",
    columns: [
      { title: "Organization", field: "id", type: "org", filter: "text" },
      count("Repos", "repos"),
      count("Packages", "packages"),
      count("Images", "images"),
      count("Security boundaries", "security_boundaries"),
      count("Live services", "live_services"),
      count("Publish from CI", "ci_publishers"),
      count("Downloads / month", "downloads_last_month"),
      { title: "Last commit", field: "last_commit", type: "date" },
    ],
    sort: [{ column: "repos", dir: "desc" }],
  },
  {
    id: "packages",
    title: "Packages",
    description: "The PyPI and npm packages built from these repos, with how much they are downloaded and depended on.",
    source: "packages",
    columns: [
      { title: "System", field: "system", filter: "select" },
      { title: "Package", field: "name", type: "package", target: "id", filter: "text" },
      { title: "Repository", field: "repo", type: "repo", filter: "text" },
      downloads,
      { title: "Dependents", field: "dependents", type: "number", filter: "min" },
      lastPublished,
    ],
    sort: [{ column: "downloads_last_month", dir: "desc" }],
  },
  {
    id: "images",
    title: "Container images",
    description: "The images published on Docker Hub and Quay by these organizations, with how much they are pulled.",
    source: "images",
    columns: [
      image,
      registry,
      tag,
      org,
      { title: "Repository", field: "repo", type: "repo", filter: "text" },
      pulls,
      lastPublished,
    ],
    sort: [{ column: "pulls", dir: "desc" }],
  },
  {
    id: "security-boundaries",
    title: "Security boundaries",
    description:
      "Repos whose code authenticates users, executes untrusted input or sits between users and a system. " +
      "Most downloaded first.",
    source: "repos",
    filter: (r) => r.security_boundary,
    columns: [
      repo,
      org,
      { title: "Security boundary", field: "security_boundary", type: "text", filter: "text" },
      downloads,
      { title: "Dependents", field: "dependents", type: "number", filter: "min" },
      count("Run unpinned by", "used_in_ci"),
      packages,
    ],
    sort: [{ column: "downloads_last_month", dir: "desc" }],
  },
  {
    id: "live-services",
    title: "Live services",
    description: "Repos that deploy a service somewhere on the internet: a website, a hub, a demo.",
    source: "repos",
    filter: (r) => r.live_service,
    columns: [
      repo,
      org,
      kind,
      { title: "Live service", field: "live_service", type: "text", filter: "text" },
      description,
    ],
    sort: [{ column: "name", dir: "asc" }],
  },
  {
    id: "used-in-ci",
    title: "Most used in CI",
    description:
      "Repos whose code other repos run without pinning a commit (an action used through a tag or branch, or a " +
      "build requirement). A compromise of one of these reaches all of those repos.",
    source: "repos",
    filter: (r) => r.used_in_ci > 0,
    columns: [
      repo,
      org,
      count("Run unpinned by", "used_in_ci"),
      count("Via CI", "via_ci", (r) => r.used_by.ci.length),
      count("Via build", "via_build", (r) => r.used_by.build.length),
      count("Pinned to a commit", "pinned", (r) => r.used_by.ci_pinned.length),
      {
        title: "Run by",
        field: "run_by",
        type: "list",
        of: "repo",
        width: 360,
        accessor: (r) => [...new Set([...r.used_by.ci, ...r.used_by.build])],
      },
      downloads,
    ],
    sort: [{ column: "used_in_ci", dir: "desc" }],
  },
  {
    id: "stale-repos",
    title: "Stale repos",
    description: "Repos with no commit for a number of days (counted from the day the data was fetched).",
    source: "repos",
    params: [{ name: "days", label: "Days without a commit", default: 365 }],
    needs: "last_commit",
    hint: MISSING_COMMIT,
    filter: (r, params, ctx) => r.last_commit && ctx.daysSince(r.last_commit) >= params.days,
    columns: [
      repo,
      org,
      kind,
      { title: "Last commit", field: "last_commit", type: "date" },
      count("Days since", "days_since", (r, ctx) => ctx.daysSince(r.last_commit)),
      downloads,
      packages,
    ],
    sort: [{ column: "last_commit", dir: "asc" }],
  },
  {
    id: "stale-packages",
    title: "Stale packages",
    description: "Packages with no release for a number of days (counted from the day the data was fetched).",
    source: "packages",
    params: [{ name: "days", label: "Days without a release", default: 365 }],
    needs: "last_published",
    hint: MISSING_PACKAGE_DATES,
    filter: (p, params, ctx) => p.last_published && ctx.daysSince(p.last_published) >= params.days,
    columns: [
      { title: "System", field: "system", filter: "select" },
      { title: "Package", field: "name", type: "package", target: "id", filter: "text" },
      { title: "Repository", field: "repo", type: "repo", filter: "text" },
      lastPublished,
      count("Days since", "days_since", (p, ctx) => ctx.daysSince(p.last_published)),
      downloads,
      { title: "Dependents", field: "dependents", type: "number", filter: "min" },
    ],
    sort: [{ column: "last_published", dir: "asc" }],
  },
  {
    id: "stale-images",
    title: "Stale images",
    description: "Images not published for a number of days (counted from the day the data was fetched).",
    source: "images",
    params: [{ name: "days", label: "Days without a publish", default: 365 }],
    needs: "last_published",
    hint: MISSING_IMAGE_DATES,
    filter: (i, params, ctx) => i.last_published && ctx.daysSince(i.last_published) >= params.days,
    columns: [
      image,
      registry,
      org,
      { title: "Repository", field: "repo", type: "repo", filter: "text" },
      lastPublished,
      count("Days since", "days_since", (i, ctx) => ctx.daysSince(i.last_published)),
      pulls,
    ],
    sort: [{ column: "last_published", dir: "asc" }],
  },
  {
    id: "images-without-repo",
    title: "Images without a repo",
    description: "Images that no repo of the inventory is known to build, mostly older ones. Most pulled first.",
    source: "images",
    filter: (i) => !i.repo,
    columns: [image, registry, tag, org, pulls, lastPublished],
    sort: [{ column: "pulls", dir: "desc" }],
  },
  {
    id: "publishes-from-ci",
    title: "Publishes from CI",
    description:
      "Repos with a workflow that publishes something (to PyPI, npm, a container registry, a website, ...), " +
      "and the secrets those workflows use.",
    source: "repos",
    filter: (r) => r.workflows.publishes.length > 0,
    columns: [
      repo,
      org,
      { title: "Publishes to", field: "publishes", type: "list", accessor: (r) => r.workflows.publishes },
      { title: "Secrets", field: "secrets", type: "list", width: 240, accessor: (r) => r.workflows.secrets },
      count("Workflows", "workflows", (r) => r.workflows.count),
      packages,
      downloads,
    ],
    sort: [{ column: "downloads_last_month", dir: "desc" }],
  },
];
