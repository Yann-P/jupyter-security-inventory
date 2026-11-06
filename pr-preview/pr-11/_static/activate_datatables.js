// Copyright (c) 2023 Varun Sharma
//
// SPDX-License-Identifier: MIT

$(document).ready( function () {
    $.extend( $.fn.dataTable.defaults,
        {"pageLength": 50, "order": [], "initComplete": initTable},
    );

    $(`table.sphinx-datatable`).filter(':not(.dataTable)').DataTable(
        {},
    );
} );