// Small helpers shared by the pages: building DOM safely, building links, and the column "types" that views name.
//
// Security rule: data (descriptions, names, ...) is untrusted text from GitHub and the registries. It only ever reaches
// the page through h() children (text nodes) or Tabulator's built-in escaping formatters, never through innerHTML. The
// only URLs we build are the ones below, from an id plus a fixed prefix, and h() refuses any other href.

const ALLOWED_HREF = /^(#\/|https:\/\/(github\.com|pypi\.org|www\.npmjs\.com|hub\.docker\.com|quay\.io)\/)/;
const seg = encodeURIComponent;
const path = (id) => id.split("/").map(seg).join("/");

/** h("a", {href: "#/"}, "text", child) -> element. Strings become text nodes; null/false children are skipped. */
export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (name.startsWith("on")) el.addEventListener(name.slice(2), value);
    else if (name === "class") el.className = value;
    else if (name === "href" && !ALLOWED_HREF.test(value)) throw new Error(`refusing to link to ${value}`);
    else el.setAttribute(name, value === true ? "" : value);
  }
  el.append(...kids.flat(Infinity).filter((kid) => kid != null && kid !== false));
  return el;
}

// Pages of this site. A package id is "SYSTEM:name" (PYPI:comm, NPM:@jupyter/ydoc).
export const page = {
  repo: (id) => "#/repo/" + path(id),
  package: (id) => "#/package/" + seg(id),
  org: (id) => "#/org/" + seg(id),
  view: (id, query = "") => `#/view/${seg(id)}${query ? "?" + query : ""}`,
};

// Pages elsewhere. An image id is "registry/org/name" (quay.io/jupyterhub/k8s-hub).
const IMAGE_PAGES = { "docker.io": "https://hub.docker.com/r/", "quay.io": "https://quay.io/repository/" };
export const elsewhere = {
  github: (repoId) => "https://github.com/" + path(repoId),
  commit: (repoId, sha) => `https://github.com/${path(repoId)}/commit/${seg(sha)}`,
  registry(packageId) {
    const [system, ...rest] = packageId.split(":");
    const name = rest.join(":");
    if (system === "PYPI") return `https://pypi.org/project/${seg(name)}/`;
    return `https://www.npmjs.com/package/${path(name).replace(/^%40/, "@")}`; // scoped names keep their @
  },
  image(imageId) {
    const [registry, ...rest] = imageId.split("/");
    return IMAGE_PAGES[registry] && IMAGE_PAGES[registry] + path(rest.join("/")); // undefined: no link, only text
  },
};

/** A link to another page of this site: link("repo", "jupyterlab/jupyterlab"). */
export const link = (kind, id, label = id) => h("a", { href: page[kind](id) }, label);

/** A link to GitHub, PyPI, npm, Docker Hub or Quay. */
export const external = (url, label) => h("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, label);

// A link to the page of a record: here on this site, or for an image at its registry (it has no page of its own).
const linkTo = (kind, id, label = id) =>
  kind === "image" ? external(elsewhere.image(id), label) : link(kind, id, label);

const numbers = new Intl.NumberFormat("en-US");
export const formatNumber = (n) => (n == null ? "" : numbers.format(n));
export const formatDate = (iso) => (iso ? String(iso).slice(0, 10) : ""); // 2026-10-27T12:00:00Z -> 2026-10-27

// A spreadsheet runs text that starts with = + - @ as a formula; the free text of a CSV download is made harmless.
const csvSafe = (text) => (typeof text === "string" && /^[=+\-@\t\r]/.test(text) ? "'" + text : text);

// ---------------------------------------------------------------------------------------------------------------
// Column types. A view column is {title, field, type, filter, width, ...} (see views.js); `type` picks one of these,
// each returning the Tabulator column properties for it. The default formatter of Tabulator escapes its input.

const lastWhenEmpty = { alignEmptyValues: "bottom" }; // rows without a value never lead a sort, in either direction

const compareText = (a, b) => String(a).localeCompare(String(b), "en", { sensitivity: "base" });

function linkColumn(kind) {
  // column.target names the field that holds the id when it is not the displayed field
  return (column) => {
    const idField = column.target ?? column.field;
    return {
      accessorDownload: (value, row) => row[idField], // the CSV has the id, not the short name
      formatter: (cell) => (cell.getValue() ? linkTo(kind, cell.getData()[idField], String(cell.getValue())) : ""),
      // repos are shown by name next to their org column but sorted as "org/name" (a column that shows the id sorts
      // as plain text, which keeps its empty values last: an image can have no repo)
      ...(kind === "repo" &&
        column.target && {
          sorter: (a, b, rowA, rowB) => compareText(rowA.getData()[idField], rowB.getData()[idField]),
        }),
    };
  };
}

const TYPES = {
  string: () => ({}), // short text
  text: () => ({ width: 300, cssClass: "long-text", accessorDownload: csvSafe }), // long free text, wrapped
  number: () => ({
    sorter: "number",
    hozAlign: "right",
    headerHozAlign: "right",
    formatter: (cell) => formatNumber(cell.getValue()),
  }),
  percent: () => ({
    // a share between 0 and 1
    sorter: "number",
    hozAlign: "right",
    headerHozAlign: "right",
    formatter: (cell) => `${Math.round(cell.getValue() * 100)}%`,
  }),
  date: () => ({ formatter: (cell) => formatDate(cell.getValue()), accessorDownload: formatDate }),
  repo: linkColumn("repo"),
  package: linkColumn("package"),
  org: linkColumn("org"),
  image: linkColumn("image"),
  // a list of strings; with `of: "repo"` (or "package") every item links to its page, with "image" to its registry;
  // `max` items are shown
  list: (column) => ({
    sorter: "array",
    cssClass: "long-text",
    width: 220, // wrapped cells need a width: Tabulator would measure them as narrow as possible
    accessorDownload: (items) => (items ?? []).join("; "),
    formatter: (cell) => {
      const items = cell.getValue() ?? [];
      if (!items.length) return "";
      const shown = items.slice(0, column.max ?? 6).map((item) => (column.of ? linkTo(column.of, item) : item));
      const more = items.length - shown.length;
      return h(
        "span",
        {},
        shown.flatMap((part, i) => (i ? [", ", part] : [part])),
        more > 0 && ` and ${formatNumber(more)} more`,
      );
    },
  }),
};

// Header filters. A view column says `filter: "text" | "select" | "min"`.
const atLeast = (wanted, actual) => actual != null && actual >= Number(wanted);
const FILTERS = {
  text: { headerFilter: "input", headerFilterPlaceholder: "contains" },
  select: {
    headerFilter: "list",
    // Tabulator writes list items with innerHTML unless the formatter hands it an element: values are untrusted
    headerFilterParams: {
      valuesLookup: true,
      clearable: true,
      sort: "asc",
      itemFormatter: (label) => h("span", {}, String(label)),
    },
    headerFilterFunc: "=",
    headerFilterPlaceholder: "any",
  },
  min: { headerFilter: "number", headerFilterPlaceholder: "at least", headerFilterFunc: atLeast },
};

export function tabulatorColumn(column) {
  const type = TYPES[column.type ?? "string"];
  if (!type) throw new Error(`unknown column type "${column.type}" in column "${column.title}"`);
  if (column.filter && !FILTERS[column.filter])
    throw new Error(`unknown filter "${column.filter}" in column "${column.title}"`);
  return {
    title: column.title,
    field: column.field,
    sorter: "string",
    sorterParams: lastWhenEmpty,
    ...type(column),
    ...(column.width && { width: column.width }),
    ...(column.filter && FILTERS[column.filter]),
  };
}

/** All the text of a row, lower case: what the free-text search looks at. */
export function searchText(row, columns) {
  const texts = columns.map((column) => row[column.field]);
  return [row.id, ...texts]
    .map((value) => (Array.isArray(value) ? value.join(" ") : (value ?? "")))
    .join(" ")
    .toLowerCase();
}
