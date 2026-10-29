// The one place that creates Tabulator tables, so every table on the site sorts, filters and pages the same way.
/* global Tabulator */
import { searchText, tabulatorColumn } from "./cells.js";

/**
 * Show `rows` in a Tabulator table inside the (already attached) element `el`.
 *   columns  view-style column specs (see views.js)
 *   sort     [{column: "field", dir: "asc" | "desc"}]
 *   state    what snapshot() returned earlier: sort, header filters, search and page to come back to
 *   paged    false for a small table that never needs pages
 *   onCount  called with the number of rows that pass the filters
 * Returns {table, snapshot, search, setRows, destroy}.
 */
export function createTable(el, { rows, columns, sort = [], state = {}, paged = true, onCount = () => {} }) {
  const prepared = (list) => list.map((row) => ({ ...row, _text: searchText(row, columns) }));
  let built = false;
  let query = "";
  const table = new Tabulator(el, {
    data: prepared(rows),
    columns: columns.map(tabulatorColumn),
    // columns as wide as their content; a wide table scrolls inside its box (fitDataStretch squeezes the last column)
    layout: "fitDataFill",
    initialSort: state.sort ?? sort,
    initialHeaderFilter: state.filters,
    placeholder: "No rows match.",
    pagination: paged,
    paginationSize: state.pageSize ?? 50,
    paginationSizeSelector: [25, 50, 100, 250, true], // true is "All"
    paginationInitialPage: state.page ?? 1,
  });
  const count = () => table.getDataCount("active");

  /** Free-text search: every word must occur somewhere in the row. Header filters keep working beside it. */
  function search(text) {
    query = text;
    const words = text.toLowerCase().split(/\s+/).filter(Boolean);
    if (words.length) table.setFilter((row) => words.every((word) => row._text.includes(word)));
    else table.clearFilter(false); // false: keep the header filters
  }

  table.on("tableBuilt", () => {
    built = true;
    for (const col of el.querySelectorAll(".tabulator-col")) {
      const title = col.querySelector(".tabulator-col-title")?.textContent ?? "";
      for (const input of col.querySelectorAll(".tabulator-header-filter input, .tabulator-header-filter select")) {
        input.setAttribute("aria-label", `Filter ${title}`);
      }
      if (col.classList.contains("tabulator-sortable")) col.tabIndex = 0; // so that the keyboard can sort too
    }
    if (state.search) search(state.search);
    onCount(count());
  });
  // count what the event says: table.getDataCount("active") is not updated yet while it fires
  table.on("dataFiltered", (filters, passing) => built && onCount(passing.length));
  el.addEventListener("keydown", (event) => {
    if (event.target.classList?.contains("tabulator-col") && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      event.target.click();
    }
  });

  return {
    table,
    search,
    snapshot() {
      if (!built) return state;
      return {
        sort: table.getSorters().map(({ field, dir }) => ({ column: field, dir })),
        filters: table.getHeaderFilters().map(({ field, value }) => ({ field, value })),
        search: query,
        page: table.getPage() || 1,
        pageSize: table.getPageSize(),
      };
    },
    setRows: (list) => table.setData(prepared(list)).then(() => onCount(count())),
    destroy: () => table.destroy(),
  };
}
