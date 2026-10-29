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

/* A table of 10 rows or fewer, the smallest page size, fits on one page: its length menu, search box, count and
   pager only take room. Sorting stays. */
function hideControlsOfSmallTable(api) {
  if (api.rows().count() <= 10) $(api.table().container()).find(".dt-layout-row:not(.dt-layout-table)").hide();
}

/* Adds an "organization" dropdown next to the search box of the tables that have the filter-by-org class.
   It filters the table's "organization" column. conf.py hands it to DataTables as its initComplete option. */
function filterByOrg(settings) {
  const api = settings.api;
  if (!$(api.table().node()).hasClass("filter-by-org")) return;

  const headers = api.columns().header().toArray().map((th) => $(th).text().trim());
  const column = api.column(headers.indexOf("organization"));
  const orgs = [...new Set(column.data().toArray().map((cell) => $("<div>").html(cell).text().trim()))].sort();

  const select = $("<select>", { "aria-label": "Filter by organization", class: "dt-input org-filter" })
    .append($("<option>", { value: "", text: "All organizations" }))
    .append(orgs.map((org) => $("<option>", { value: org, text: org })))
    .on("change", function () {
      const org = this.value;
      column.search(org ? "^" + $.fn.dataTable.util.escapeRegex(org) + "$" : "", true, false).draw();
    });
  $(api.table().container()).find(".dt-search").prepend(select);
}

/* conf.py hands this to DataTables as its initComplete option. */
function initTable(settings) {
  hideControlsOfSmallTable(settings.api);
  filterByOrg(settings);
}
