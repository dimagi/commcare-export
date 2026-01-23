# Documentation for AI Coding Assistants

## Commands

* Run tests: `uv run pytest -m "not dbtest" [path/to/file.py::Class::method]`
* Check typing: `uv run mypy commcare_export/ tests/`
* Check linting: `uv run ruff check`
* Format: `uv run ruff format <path/to/file.py>`
* Sort imports `uv run ruff check --select I --fix <path/to/file.py>`


## Tech Stack

See @pyproject.toml


## Coding Style

See @CONTRIBUTING.md
