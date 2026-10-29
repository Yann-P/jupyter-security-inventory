---
html_theme.sidebar_secondary.remove: true
---

# Container images

Pulls are all-time Docker Hub counts and include CI; Quay publishes none. The tag is `latest`, or the newest when there is none.

[images.txt](https://raw.githubusercontent.com/Yann-P/jupyter-security-inventory/main/output/images.txt) lists the images for vulnerability scanners ([how to scan them](about.md)).

```{csv-table}
:file: _generated/images.csv
:header-rows: 1
:class: sphinx-datatable filter-by-org
```
