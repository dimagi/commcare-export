# Documentation for AI Coding Assistants

## Commits

Each commit should do exactly one thing so that its diff is easy to
review. If a task involves multiple changes, split them into separate
commits. For example, whenever code is moved and changed, or a file is
renamed and changed, do the move or the rename in one commit and make
the changes in another. If files need to be reformatted with ruff, do
that and commit before making code changes.

## Commands

The `commcare-export` codebases uses a virtualenv managed by uv. Prefix
commands with `uv run ...` to run them in the virtualenv.

* Run tests: `uv run pytest -m "not dbtest" [path/to/file.py::Class::method]`
* Check typing: `uv run mypy commcare_export/ tests/`
* Check linting: `uv run ruff check`
* Format: `uv run ruff format <path/to/file.py>`
* Sort imports `uv run ruff check --select I --fix <path/to/file.py>`


## Tech Stack

See @pyproject.toml


## Coding Style

See @CONTRIBUTING.md
