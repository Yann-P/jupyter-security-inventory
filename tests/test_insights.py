"""Tests for docs/insights.py, which writes the site's pages."""

import insights


def test_plain_keeps_text_from_repos_from_becoming_html_or_markdown():
    assert insights.plain("<script>") == "\\<script\\>"
    assert insights.plain("{{ repos }}") == "\\{\\{ repos \\}\\}"
    assert insights.plain("[click](evil)") == "\\[click\\]\\(evil\\)"  # a link the model was tricked into writing


def test_org_summary_reads_as_one_sentence():
    counts = {"repos": 35, "packaged": 6, "boundaries": 1, "services": 0}
    assert insights.org_summary("jupyter-book", counts) == (
        "[github.com/jupyter-book](https://github.com/jupyter-book) has 35 public repositories: "
        "6 publish a package and 1 is a security boundary."
    )
