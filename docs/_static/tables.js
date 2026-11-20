/* Tweaks to the DataTables tables. conf.py loads this after DataTables and before the tables are drawn. */

/* The columns of counts have thousands separators and links, and empty cells for the repos that publish no
   package. DataTables' html-num-fmt type fits the first two, but rejects a column with an empty cell, so such a
   column would be sorted as text. Accept empty cells, like its html-num type does. */
const numFmt = DataTable.type("html-num-fmt");
const numFmtAllOf = numFmt.detect.allOf;
DataTable.type("html-num-fmt", "detect", {
  oneOf: numFmt.detect.oneOf,
  allOf: (cell, settings) => cell === "" || numFmtAllOf(cell, settings),
});

/* A table of 10 rows or fewer, the smallest page size, fits on one page: its search box, count, page size and pager
   only take room. Sorting, the filters and the download link stay. */
function hideControlsOfSmallTable(api) {
  if (api.rows().count() > 10) return;
  $(api.table().container()).find(".dt-search > label, .dt-search > input, .dt-info, .dt-length, .dt-paging").hide();
}

/* Hides a row of controls left with nothing to show, like the top row of a small table without filters. */
function hideEmptyRows(api) {
  $(api.table().container())
    .children(".dt-layout-row:not(.dt-layout-table)")
    .filter((_, row) => !$(row).find("a, input, select, .dt-info").filter(":visible").length)
    .hide();
}

/* The "Download Full CSV" link above a table moves to the end of its bottom row, after the pager. */
function moveDownload(api) {
  const container = $(api.table().container());
  const paragraph = container.parent().prev("p").has("a.download");
  if (!paragraph.length) return;
  const row = container.children(".dt-layout-row").last();
  let end = row.children(".dt-layout-end");
  if (!end.length) end = $("<div>", { class: "dt-layout-cell dt-layout-end" }).appendTo(row);
  end.append(paragraph.find("a.download").addClass("table-download"));
  paragraph.remove();
}

/* Adds a dropdown next to the search box of the tables that have a filter-by-... class. It filters the table's
   column of that name. Each is put first in turn, so they show in reverse order: owner, organization, status.
   The page's URL can pick values, like ?owner=Jupyter%20Book&status=missing, which the counts link with. */
const FILTERS = [
  ["filter-by-status", "status", "All statuses", "status"],
  ["filter-by-org", "organization", "All organizations", "org"],
  ["filter-by-owner", "owner", "All owners", "owner"],
];

function addFilters(settings) {
  const api = settings.api;
  const headers = api.columns().header().toArray().map((th) => $(th).text().trim());
  for (const [cls, header, all, param] of FILTERS) {
    const index = headers.indexOf(header);
    if (!$(api.table().node()).hasClass(cls) || index < 0) continue;

    const column = api.column(index);
    const values = [...new Set(column.data().toArray().map((cell) => $("<div>").html(cell).text().trim()))].sort();
    const select = $("<select>", { "aria-label": `Filter by ${header}`, class: "dt-input table-filter" })
      .append($("<option>", { value: "", text: all }))
      .append(values.map((value) => $("<option>", { value, text: value })))
      .on("change", function () {
        const value = this.value;
        column.search(value ? "^" + $.fn.dataTable.util.escapeRegex(value) + "$" : "", true, false).draw();
      });
    $(api.table().container()).find(".dt-search").prepend(select);
    const wanted = new URLSearchParams(location.search).get(param);
    if (values.includes(wanted)) select.val(wanted).trigger("change");
  }
}

/* The page's URL can keep only the repositories where a column is filled in, like ?has=security%20boundary, which
   the counts of the owners, the organizations and the summary sentences link with. Only the repository tables are
   filtered; one that has none of those rows is hidden, like the documentation table, which has no "package" column.
   A note at the top of the section says what is shown. */
const HAS = {
  package: "that publish a package",
  "security boundary": "that are security boundaries",
  "live service": "that deploy a live service",
};

function keepFilledIn(api) {
  const column = new URLSearchParams(location.search).get("has");
  const table = $(api.table().node());
  const section = table.closest("section#repositories");
  if (!(column in HAS) || !section.length) return;

  const headers = api.columns().header().toArray().map((th) => $(th).text().trim());
  const index = headers.indexOf(column);
  if (index >= 0) api.column(index).search("\\S", true, false).draw();
  if (index < 0 || api.rows({ search: "applied" }).count() === 0) table.closest("section#repositories section").hide();

  if (!section.find(".has-filter").length) {
    const all = $("<a>", { href: location.pathname + "#repositories", text: "Show all" });
    $("<p>", { class: "has-filter", text: `Only the repositories ${HAS[column]}. ` })
      .append(all)
      .insertAfter(section.children("h2").first());
  }
}

/* conf.py hands this to DataTables as its initComplete option. */
function initTable(settings) {
  hideControlsOfSmallTable(settings.api);
  addFilters(settings);
  moveDownload(settings.api);
  hideEmptyRows(settings.api);
  keepFilledIn(settings.api);
}
