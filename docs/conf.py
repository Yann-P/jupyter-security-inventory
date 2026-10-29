import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import insights  # noqa: E402

project = "Jupyter Security Inventory"
extensions = ["myst_parser", "sphinxcontrib.jquery", "sphinx_datatables"]
html_theme = "pydata_sphinx_theme"
html_title = project
html_theme_options = {
    "github_url": "https://github.com/Yann-P/jupyter-security-inventory",
    "navbar_center": [],  # the navigation is in the left sidebar instead
    "secondary_sidebar_items": ["page-toc"],  # pages with a big table remove it, in their front matter
    "footer_start": [],
    "footer_end": [],
    "show_prev_next": False,  # the order of the pages is the sidebar's, and means nothing across organizations
}
templates_path = ["_templates"]
html_sidebars = {"**": ["site-nav"]}
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_js_files = [("tables.js", {"priority": 800})]  # after DataTables, which is at 500
exclude_patterns = ["_build", "_generated"]

myst_enable_extensions = ["substitution", "attrs_inline"]  # attrs_inline: [text]{.class}, for the row colors
myst_heading_anchors = 3  # so that [Packages](#packages) links to a heading, as on the organization pages
myst_substitutions = insights.build()

# The big tables are sortable and searchable with DataTables, loaded from cdn.datatables.net.
datatables_version = "3.1.4"
# Keep the order the tables are generated in. initTable is defined in _static/tables.js, so this has to stay a string.
datatables_options = '{"pageLength": 50, "order": [], "initComplete": initTable}'
