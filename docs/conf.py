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
}
templates_path = ["_templates"]
html_sidebars = {"**": ["site-nav"]}
html_static_path = ["_static"]
html_css_files = ["custom.css"]
exclude_patterns = ["_build", "_generated"]

myst_enable_extensions = ["substitution", "attrs_inline"]  # attrs_inline: [text]{.class}, for the row colors
myst_substitutions = insights.build()

# The big tables are sortable and searchable with DataTables, loaded from cdn.datatables.net.
datatables_version = "3.1.4"
datatables_options = {"pageLength": 50, "order": []}  # keep the order the tables are generated in
