// Loads the data, routes #/ URLs to pages and draws them. What the table views show is declared in views.js.
//
//   #/                        home: the list of views
//   #/view/<id>?param=value   a table view
//   #/repo/<org>/<name>   #/package/<SYSTEM:name>   #/org/<org>   one record and what it is related to
//                             (an image has no page of its own: it links to its registry, its repo and its org)
import { elsewhere, external, formatDate, formatNumber, h, link, page } from "./cells.js";
import { createTable } from "./table.js";
import { views } from "./views.js";

const main = document.querySelector("main");
const DAY = 86_400_000;
const plural = (n, word, many = word + "s") => `${formatNumber(n)} ${n === 1 ? word : many}`;

// ---------------------------------------------------------------------------------------------------------------
// Data: four JSON files joined by ids. ctx is what views and pages get to look at.

let ctx;

async function loadData() {
  const get = async (name) => {
    const response = await fetch(`data/${name}.json`);
    if (!response.ok) throw new Error(`data/${name}.json: HTTP ${response.status}`);
    return response.json();
  };
  const [repos, packages, images, meta] = await Promise.all([
    get("repos"),
    get("packages"),
    get("images"),
    get("meta"),
  ]);
  const asOf = Date.parse(meta.fetched_on); // "today" for staleness is the day the data was fetched
  const data = {
    meta,
    repos,
    packages,
    images,
    repoById: new Map(repos.map((repo) => [repo.id, repo])),
    packageById: new Map(packages.map((pkg) => [pkg.id, pkg])),
    imageById: new Map(images.map((image) => [image.id, image])),
    daysSince: (iso) => (iso ? Math.max(0, Math.floor((asOf - Date.parse(iso)) / DAY)) : null),
  };
  data.orgs = deriveOrgs(data);
  data.orgById = new Map(data.orgs.map((org) => [org.id, org]));
  return data;
}

const latest = (dates) => dates.filter(Boolean).sort().at(-1) ?? null; // ISO dates sort as text

/** There is no orgs.json: an organization is what its repos add up to. */
function deriveOrgs({ repos, packageById, images, meta }) {
  const names = [...new Set([...meta.orgs, ...repos.map((repo) => repo.org)])].sort();
  return names.map((id) => {
    const mine = repos.filter((repo) => repo.org === id);
    const packageIds = mine.flatMap((repo) => repo.packages);
    const downloads = packageIds.map((pid) => packageById.get(pid)?.downloads_last_month ?? 0);
    return {
      id,
      repos: mine.length,
      packages: packageIds.length,
      images: images.filter((image) => image.org === id).length, // by registry namespace, which is an organization
      security_boundaries: mine.filter((repo) => repo.security_boundary).length,
      live_services: mine.filter((repo) => repo.live_service).length,
      ci_publishers: mine.filter((repo) => repo.workflows.publishes.length).length,
      downloads_last_month: downloads.reduce((a, b) => a + b, 0),
      last_commit: latest(mine.map((repo) => repo.last_commit)),
    };
  });
}

// ---------------------------------------------------------------------------------------------------------------
// Tables. A page builds its elements first and its tables once they are in the document (Tabulator measures them).

let mounts = []; // functions that create the tables of the page being built

function tableBox(options) {
  const box = h("div", { class: "table" });
  mounts.push(() => createTable(box, options));
  return box;
}

/** The records of a view with its filter applied and its computed columns added. */
function rowsFor(view, params) {
  return ctx[view.source]
    .filter((record) => !view.filter || view.filter(record, params, ctx))
    .map((record) => {
      const row = { ...record };
      for (const column of view.columns) if (column.accessor) row[column.field] = column.accessor(record, ctx, params);
      return row;
    });
}

const defaultParams = (view) => Object.fromEntries((view.params ?? []).map((p) => [p.name, p.default]));
const noDates = (view) => view.needs && !ctx[view.source].some((record) => record[view.needs] != null);
const savedState = new Map(); // sort, filters and page of the tables we left, so that "back" finds them as they were

// ---------------------------------------------------------------------------------------------------------------
// Pages. Each returns {title, content, leave?}; leave() runs when the visitor goes elsewhere.

function homePage() {
  const cards = views.map((view) => {
    const rows = noDates(view) ? null : rowsFor(view, defaultParams(view)).length;
    return h(
      "li",
      { class: "card" },
      h("h2", {}, h("a", { href: page.view(view.id) }, view.title)),
      h("p", {}, view.description),
      h("p", { class: "muted" }, rows === null ? "No dates in the data yet" : plural(rows, "row")),
    );
  });
  const { meta, repos, packages, images, orgs } = ctx;
  const summary =
    `${plural(repos.length, "public repository", "public repositories")}, ${plural(packages.length, "package")} ` +
    `and ${plural(images.length, "container image")} in ${plural(orgs.length, "GitHub organization")}, ` +
    `fetched on ${meta.fetched_on}.`;
  return {
    title: "Jupyter security inventory",
    content: [
      h("h1", {}, "Jupyter security inventory"),
      h("p", { class: "lede" }, summary),
      h("ul", { class: "cards" }, cards),
    ],
  };
}

/** Parameter values from the URL; anything that is not a number of at least 0 keeps the default. */
function readParams(view, query) {
  const params = defaultParams(view);
  for (const name of Object.keys(params)) {
    const text = query.get(name);
    if (text?.trim() && Number.isFinite(Number(text)) && Number(text) >= 0) params[name] = Number(text);
  }
  return params;
}

const dateName = (view) => view.needs.replace("_", " "); // last_commit -> last commit

function viewPage(view, query) {
  const params = readParams(view, query);
  const intro = [h("h1", {}, view.title), h("p", { class: "lede" }, view.description)];
  if (noDates(view)) {
    const total = plural(ctx[view.source].length, view.source.replace(/s$/, ""));
    const message = `None of the ${total} has a ${dateName(view)} date yet, so this view cannot tell which are stale.`;
    return { title: view.title, content: [...intro, h("p", { class: "notice" }, message, " ", view.hint)] };
  }

  let rows = rowsFor(view, params);
  let controller;
  const box = h("div", { class: "table" });
  const counter = h("span", { class: "count", role: "status" });
  const showCount = (n) =>
    (counter.textContent = n === rows.length ? plural(n, "row") : `${n} of ${plural(rows.length, "row")}`);
  const stateKey = () => view.id + JSON.stringify(params); // other parameters, other rows: other state
  const state = savedState.get(stateKey()) ?? {};

  const inputs = (view.params ?? []).map((p) =>
    h(
      "label",
      {},
      p.label,
      h("input", {
        type: "number",
        min: 0,
        value: params[p.name],
        oninput(event) {
          if (!(event.target.valueAsNumber >= 0)) return; // empty or negative: wait for a real number
          params[p.name] = event.target.valueAsNumber;
          // replaceState, not a new hash: no re-render, no history entry per keystroke, and the URL stays shareable
          history.replaceState(null, "", page.view(view.id, new URLSearchParams(params).toString()));
          rows = rowsFor(view, params);
          controller.setRows(rows);
        },
      }),
    ),
  );
  const search = h("input", {
    type: "search",
    placeholder: "words in any column",
    autocomplete: "off",
    value: state.search ?? "",
  });
  search.addEventListener("input", () => controller.search(search.value));
  const unlisted = view.needs ? ctx[view.source].filter((record) => record[view.needs] == null).length : 0;

  mounts.push(
    () => (controller = createTable(box, { rows, columns: view.columns, sort: view.sort, state, onCount: showCount })),
  );
  return {
    title: view.title,
    content: [
      ...intro,
      inputs.length > 0 && h("form", { class: "params", onsubmit: (event) => event.preventDefault() }, inputs),
      unlisted > 0 &&
        h("p", { class: "muted" }, `${plural(unlisted, "record")} without a ${dateName(view)} date left out.`),
      h(
        "div",
        { class: "toolbar" },
        h("label", {}, "Search", search),
        counter,
        h(
          "button",
          { type: "button", onclick: () => controller.table.download("csv", `${view.id}.csv`) },
          "Download CSV",
        ),
      ),
      box,
    ],
    leave: () => controller && savedState.set(stateKey(), controller.snapshot()),
  };
}

const facts = (pairs) =>
  h(
    "dl",
    { class: "facts" },
    pairs.flatMap(([term, value]) => [h("dt", {}, term), h("dd", {}, value)]),
  );
const section = (title, ...content) => h("section", {}, h("h2", {}, title), ...content);
const none = (text) => h("p", { class: "muted" }, text);
const crumbs = (...items) =>
  h(
    "nav",
    { class: "crumbs", "aria-label": "Breadcrumb" },
    items.flatMap((item, i) => (i ? [" / ", item] : [item])),
  );
const home = () => h("a", { href: "#/" }, "Home");

const packageColumns = [
  { title: "Package", field: "name", type: "package", target: "id" },
  { title: "System", field: "system" },
  { title: "Downloads / month", field: "downloads_last_month", type: "number" },
  { title: "Dependents", field: "dependents", type: "number" },
  { title: "Last published", field: "last_published", type: "date" },
];
const packageTable = (ids) =>
  tableBox({
    rows: ids.map((id) => ctx.packageById.get(id)).filter(Boolean),
    columns: packageColumns,
    sort: [{ column: "downloads_last_month", dir: "desc" }],
    paged: ids.length > 50,
  });

const imageColumns = [
  { title: "Image", field: "id", type: "image" },
  { title: "Tag", field: "tag" },
  { title: "All-time pulls", field: "pulls", type: "number" },
  { title: "Last published", field: "last_published", type: "date" },
];
const imageTable = (ids, columns = imageColumns) =>
  tableBox({
    rows: ids.map((id) => ctx.imageById.get(id)).filter(Boolean),
    columns,
    sort: [{ column: "pulls", dir: "desc" }],
    paged: ids.length > 50,
  });

// used_by and uses are {ci, ci_pinned, build}: lists of repo ids. One table, with how the repos are related.
const HOW = {
  ci: "CI action, tag or branch (unpinned)",
  ci_pinned: "CI action, pinned to a commit",
  build: "Build requirement",
};
function relatedTable(byKind) {
  const rows = Object.entries(byKind).flatMap(([kind, ids]) => ids.map((id) => ({ id, how: HOW[kind] })));
  if (!rows.length) return null;
  const columns = [
    { title: "Repository", field: "id", type: "repo" },
    { title: "How", field: "how" },
  ];
  return tableBox({ rows, columns, sort: [{ column: "id", dir: "asc" }], paged: rows.length > 50 });
}

function repoPage(repo) {
  const { workflows } = repo;
  const fileTypes = Object.entries(repo.file_types).map(([type, files]) => ({
    type,
    files,
    share: files / repo.n_files,
  }));
  return {
    title: repo.id,
    content: [
      crumbs(home(), link("org", repo.org), repo.name),
      h("h1", {}, repo.id),
      facts([
        ["Description", repo.description ?? "None"],
        ["Kind", repo.kind],
        ["Security boundary", repo.security_boundary ?? "None identified"],
        ["Rationale", repo.rationale],
        ["Live service", repo.live_service ?? "None"],
        ["Fork", repo.is_fork ? "Yes" : "No"],
        ["Last commit", formatDate(repo.last_commit) || "Not recorded yet"],
        ["Scanned at commit", external(elsewhere.commit(repo.id, repo.head), repo.head.slice(0, 7))],
        ["On GitHub", external(elsewhere.github(repo.id), `github.com/${repo.id}`)],
      ]),
      section(
        "Packages",
        repo.packages.length ? packageTable(repo.packages) : none("This repo does not publish a package."),
      ),
      section(
        "Container images",
        repo.images.length ? imageTable(repo.images) : none("No container image of the inventory is built from it."),
      ),
      section(
        "Who runs this repo's code",
        relatedTable(repo.used_by) ?? none("No other repo of the inventory uses its actions or its packages."),
      ),
      section(
        "Whose code this repo runs",
        relatedTable(repo.uses) ?? none("It uses no action or package of the inventory."),
      ),
      section(
        "Workflows",
        facts([
          ["Workflow files", formatNumber(workflows.count)],
          ["Triggers", workflows.triggers.join(", ") || "None"],
          ["Secrets used", workflows.secrets.join(", ") || "None"],
          ["Publishes to", workflows.publishes.join(", ") || "Nothing"],
        ]),
      ),
      section(
        `File types (${plural(repo.n_files, "file")})`,
        tableBox({
          rows: fileTypes,
          columns: [
            { title: "Type", field: "type" },
            { title: "Files", field: "files", type: "number" },
            { title: "Share", field: "share", type: "percent" },
          ],
          sort: [{ column: "files", dir: "desc" }],
          paged: false,
        }),
      ),
    ],
  };
}

function packagePage(pkg) {
  const siblings = (ctx.repoById.get(pkg.repo)?.packages ?? []).filter((id) => id !== pkg.id);
  return {
    title: pkg.id,
    content: [
      crumbs(home(), link("repo", pkg.repo), pkg.name),
      h("h1", {}, pkg.id),
      facts([
        ["Repository", link("repo", pkg.repo)],
        ["Registry", external(elsewhere.registry(pkg.id), pkg.system === "PYPI" ? "pypi.org" : "npmjs.com")],
        ["Downloads last month", formatNumber(pkg.downloads_last_month)],
        ["Dependents", formatNumber(pkg.dependents)],
        ["Last published", formatDate(pkg.last_published) || "Not recorded yet"],
        ["Why this repo", pkg.reason],
      ]),
      siblings.length > 0 && section("Other packages of the same repo", packageTable(siblings)),
    ],
  };
}

function orgPage(org) {
  const repos = ctx.repos.filter((repo) => repo.org === org.id);
  const columns = [
    { title: "Repository", field: "id", type: "repo", filter: "text" },
    { title: "Kind", field: "kind", filter: "select" },
    { title: "Description", field: "description", type: "text" },
    { title: "Packages", field: "packages", type: "list", of: "package" },
    { title: "Downloads / month", field: "downloads_last_month", type: "number" },
  ];
  const table = tableBox({ rows: repos, columns, sort: [{ column: "id", dir: "asc" }], paged: repos.length > 50 });
  const packageIds = repos.flatMap((repo) => repo.packages);
  const imageIds = ctx.images.filter((image) => image.org === org.id).map((image) => image.id);
  return {
    title: org.id,
    content: [
      crumbs(home(), org.id),
      h("h1", {}, org.id),
      facts([
        ["On GitHub", external(elsewhere.github(org.id), `github.com/${org.id}`)],
        ["Repos", formatNumber(org.repos)],
        ["Packages", formatNumber(org.packages)],
        ["Container images", formatNumber(org.images)],
        ["Security boundaries", formatNumber(org.security_boundaries)],
        ["Live services", formatNumber(org.live_services)],
        ["Repos that publish from CI", formatNumber(org.ci_publishers)],
        ["Downloads last month", formatNumber(org.downloads_last_month)],
      ]),
      section("Repositories", repos.length ? table : none("No repository of this organization is in the inventory.")),
      packageIds.length > 0 && section("Packages", packageTable(packageIds)),
      imageIds.length > 0 &&
        section(
          "Container images",
          imageTable(imageIds, [...imageColumns, { title: "Repository", field: "repo", type: "repo" }]),
        ),
    ],
  };
}

function notFound() {
  const content = [
    h("h1", {}, "Not found"),
    h("p", {}, "There is no such page. ", h("a", { href: "#/" }, "Back to the home page"), "."),
  ];
  return { title: "Not found", content };
}

function errorPage(error) {
  const advice = [
    "The page reads the JSON files in ",
    h("code", {}, "data/"),
    " next to it. If you opened index.html as a file, serve the folder instead: ",
    h("code", {}, "python3 -m http.server -d site"),
    ".",
  ];
  const content = [
    h("h1", {}, "Something went wrong"),
    h("p", { class: "error", role: "alert" }, String(error.message ?? error)),
    h("p", {}, ...advice),
  ];
  return { title: "Error", content };
}

// ---------------------------------------------------------------------------------------------------------------
// Router

const pages = {
  repo: { find: (rest) => rest.length === 2 && ctx.repoById.get(rest.join("/")), render: repoPage },
  package: { find: (rest) => rest.length === 1 && ctx.packageById.get(rest[0]), render: packagePage },
  org: { find: (rest) => rest.length === 1 && ctx.orgById.get(rest[0]), render: orgPage },
};

function build() {
  const [path, query = ""] = location.hash.slice(1).split("?");
  const [kind, ...rest] = path
    .split("/")
    .filter(Boolean)
    .map((part) => decodeURIComponent(part));
  if (!kind) return homePage();
  const view = kind === "view" && rest.length === 1 && views.find((v) => v.id === rest[0]);
  if (view) return viewPage(view, new URLSearchParams(query));
  const record = pages[kind]?.find(rest);
  return record ? pages[kind].render(record) : notFound();
}

let current = { tables: [] };
let firstPage = true;

function show(result) {
  const pending = mounts;
  mounts = [];
  main.replaceChildren(...[result.content].flat().filter(Boolean));
  current = { leave: result.leave, tables: pending.map((mount) => mount()) };
  document.title = result.title.startsWith("Jupyter") ? result.title : `${result.title} - Jupyter security inventory`;
  for (const a of document.querySelectorAll("#views a")) {
    if (a.getAttribute("href") === location.hash.split("?")[0]) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  if (!firstPage) {
    window.scrollTo(0, 0);
    const heading = main.querySelector("h1");
    heading.tabIndex = -1; // lets a screen reader announce the new page
    heading.focus({ preventScroll: true });
  }
  firstPage = false;
}

function route() {
  current.leave?.();
  for (const table of current.tables) table.destroy();
  current = { tables: [] };
  mounts = [];
  try {
    show(build());
  } catch (error) {
    mounts = [];
    // a URL that does not decode (URIError) is a page that does not exist
    show(error instanceof URIError ? notFound() : errorPage(error));
  }
}

async function start() {
  try {
    ctx = await loadData();
  } catch (error) {
    main.replaceChildren(...errorPage(error).content);
    return;
  }
  document
    .querySelector("#views")
    .append(...views.map((view) => h("li", {}, h("a", { href: page.view(view.id) }, view.title))));
  document.querySelector("#fetched").textContent = ctx.meta.fetched_on;
  document.querySelector(".skip").addEventListener("click", (event) => {
    event.preventDefault(); // a #main hash would be a route of its own
    main.focus();
  });
  window.addEventListener("hashchange", route);
  route();
}

start();
