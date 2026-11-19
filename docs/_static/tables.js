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

/* Adds a dropdown next to the search box of the tables that have the filter-by-org or filter-by-owner class.
   It filters the table's "organization" or "owner" column. */
const FILTERS = [
  ["filter-by-org", "organization", "All organizations"],
  ["filter-by-owner", "owner", "All owners"],
];

function addFilters(settings) {
  const api = settings.api;
  const headers = api.columns().header().toArray().map((th) => $(th).text().trim());
  for (const [cls, header, all] of FILTERS) {
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
  }
}

/* conf.py hands this to DataTables as its initComplete option. */
function initTable(settings) {
  hideControlsOfSmallTable(settings.api);
  addFilters(settings);
}
