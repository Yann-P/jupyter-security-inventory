---
html_theme.sidebar_secondary.remove: true
---

# Container images

The {{ images }} container images that Jupyter publishes on Docker Hub and Quay, each with the tag people get by default: `latest`, or the newest tag when there is none. Pull counts come from Docker Hub and include CI; Quay publishes none. The repository is the one the image's description links to, when it names one.

The list is also written as [plain text](https://raw.githubusercontent.com/Yann-P/jupyter-security-inventory/main/output/images.txt), one image per line, for vulnerability scanners. The [about page](about.md) shows how to scan it.

```{csv-table}
:file: _generated/images.csv
:header-rows: 1
:class: sphinx-datatable
```
