---
html_theme.sidebar_secondary.remove: true
---

# Container images

The {{ images }} container images that Jupyter publishes on Docker Hub and Quay, each with the tag people get by default: `latest`, or the newest tag when there is none. Choose an organization to see only its images, and click on a repository for more details. Pulls are all-time counts from Docker Hub, and include CI; Quay publishes none. The repository is the one that builds the image or that its description links to, when there is one.

The list is also written as [plain text](https://raw.githubusercontent.com/Yann-P/jupyter-security-inventory/main/output/images.txt), one image per line, for vulnerability scanners. The [about page](about.md) shows how to scan it.

```{csv-table}
:file: _generated/images.csv
:header-rows: 1
:class: sphinx-datatable filter-by-org
```
