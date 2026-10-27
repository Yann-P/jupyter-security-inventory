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
