# Working on this repo

- **Keep diffs small.** Change only what the task needs, and write generated data compactly, like one row per line.
- **Tests are pragmatic.** One test per real behavior, on the cases that could really break. No tests for trivial
  code, for the standard library, or that restate the code. A test that must change whenever someone adds a topic or a
  column is too tight. Run `pytest` before committing.
- **Comments say why, not what.** Don't comment what the code or its names already say, and don't add docstrings
  that repeat the function name. Keep the ones that explain something surprising.
- **Write short, natural English** in docs, comments, commit messages and replies: plain words, short sentences, no
  filler or jargon. Say it once.
- **Never edit `output/` by hand.** Rerun the pipeline from the step you changed (see the README) and commit the
  result. CI checks that the outputs of steps 6 to 8 match the code.
- **Format with ruff** (`pre-commit run --all-files`) and build the site with `sphinx-build -W docs docs/_build`.
