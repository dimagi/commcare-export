Development Guide
=================

*Part of [Technical Documentation](index.md)*

This guide covers setting up a development environment for CommCare
Export and understanding the codebase structure.


Setting Up Development Environment
----------------------------------

> [!NOTE]
> This guide provides detailed technical setup information. For a quick
> start guide to contributing, see
> [CONTRIBUTING.md](../CONTRIBUTING.md).

### Prerequisites

- Python 3.9 or higher
- Git
- [uv](https://docs.astral.sh/uv/)

### Installation Steps

1. Fork and clone the repository:
   ```shell
   git clone git@github.com:your-username/commcare-export.git
   cd commcare-export
   ```

2. Create and activate a virtual environment:
   ```shell
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install in development mode with test dependencies:
   ```shell
   uv pip install -e ".[test]"
   ```

4. Verify the installation:
   ```shell
   commcare-export --version
   pytest --version
   mypy --version
   ```

### Optional Dependencies

For specific database or output format support:

```shell
# PostgreSQL support
uv pip install -e ".[postgres]"

# MySQL support
uv pip install -e ".[mysql]"

# MS SQL Server support
uv pip install -e ".[odbc]"

# Excel output support
uv pip install -e ".[xlsx,xls]"

# Everything (for comprehensive development)
uv pip install -e ".[test,postgres,mysql,odbc,xlsx,xls]"
```


Project Structure
-----------------

### Main Package: `commcare_export/`

**Core Modules:**

- `cli.py` (558 lines) - Command-line interface implementation
  - Argument parsing
  - Main entry point
  - Command orchestration

- `minilinq.py` (593 lines) - MiniLinq query language core
  - Abstract syntax tree (AST) definitions
  - Query evaluation engine
  - Core language primitives

- `env.py` (639 lines) - Execution environments
  - Built-in function environment
  - JSON path environment
  - Environment composition

- `excel_query.py` (724 lines) - Excel query parsing
  - Workbook parsing
  - Query compilation to MiniLinq
  - Excel-specific logic

- `commcare_minilinq.py` (330 lines) - CommCare-specific extensions
  - CommCare HQ environment
  - API data functions
  - Pagination handling

- `commcare_hq_client.py` (333 lines) - REST API client
  - HTTP client for CommCare HQ
  - Authentication handling
  - Resource iteration

- `writers.py` (629 lines) - Output format writers
  - CSV, Excel, JSON, Markdown writers
  - SQL writer with upsert logic
  - Streaming and buffered writers

- `checkpoint.py` (523 lines) - Checkpoint management
  - Checkpoint storage and retrieval
  - Incremental export state tracking
  - Multiple checkpoint strategies

**Supporting Modules:**

- `builtin_queries.py` - Pre-built queries for users/locations
- `utils.py`, `misc.py` - Utility functions
- `exceptions.py` - Custom exception types
- `data_types.py` - Data type definitions
- `jsonpath_utils.py` - JSON path utilities
- `repeatable_iterator.py` - Iterator utilities
- `specs.py` - Query specifications
- `version.py` - Version management
- `map_format.py` - Data format mapping
- `location_info_provider.py` - Location data handling
- `utils_cli.py` - CLI utilities

### Other Directories

- `tests/` - Test suite
- `migrations/` - Alembic database migrations
- `build_exe/` - Executable building configuration
- `examples/` - Example queries and scripts
- `docs/` - Technical documentation (this directory)


Code Organization
-----------------

### MiniLinq Architecture

The MiniLinq query language has three main components:

1. **AST (`minilinq.py`)**: Abstract syntax tree defining query
   structure
   - Literal, Reference, List, Map, FlatMap, Filter, Bind, Emit, Apply

2. **Evaluation (`minilinq.py`, `env.py`)**: Query execution engine
   - Environment-based evaluation
   - Lazy evaluation where possible
   - Composable environments

3. **Extensions (`commcare_minilinq.py`)**: CommCare-specific functions
   - API data fetching
   - Pagination
   - CommCare-specific built-ins

### Data Flow

```
Excel/JSON Query
       ↓
   Parse/Load (excel_query.py)
       ↓
   MiniLinq AST (minilinq.py)
       ↓
   Evaluate with Env (env.py + commcare_minilinq.py)
       ↓
   Fetch Data (commcare_hq_client.py)
       ↓
   Transform Data (minilinq.py evaluation)
       ↓
   Write Output (writers.py)
```

### Key Design Patterns

1. **Environment Pattern**: Functions and data sources provided via
   composed environments

2. **Visitor Pattern**: AST traversal for evaluation and transformation

3. **Strategy Pattern**: Multiple writers, pagination strategies,
   checkpoint managers

4. **Builder Pattern**: Query construction from Excel/JSON sources


Code Style
----------

The project follows standard Python conventions:

- PEP 8 style guide
- Clear, descriptive names
- Docstrings for public functions


Type Hints and Type Checking
-----------------------------

Type hints are treated as documentation, and as such are used sparingly.
Use type hints when:

* A parameter's type is not obvious from its name
* It would be useful to know a parameter's class
* A function's or method's return value is not obvious from its name

### Guidelines

**When to add type hints:**
- Complex data structures
- Functions with non-obvious return types
- Public API methods and functions
- Callbacks and higher-order functions

**Best practices:**
- If you add a type hint to one parameter, add hints to all parameters
  and the return value for readability
- Use type aliases (e.g.,
  `type CredentialsType = tuple[UsernameType, PasswordType]`) where they
  clarify the purpose of a type
- As with documentation, don't add type hints where the type is obvious.

### Running Type Checks

After making changes to typed modules, ensure type correctness:

```shell
# Check all modules
mypy --install-types commcare_export/ tests/ migrations/

# Check specific file
mypy commcare_export/env.py
```


Making Changes
--------------

### Feature Development Workflow

1. **Create a feature branch** from `master`:
   ```shell
   git checkout -b my-super-duper-feature
   ```

2. **Make your changes** following the code style guidelines

3. **Write tests** for your changes:
   - Add tests to appropriate test file in `tests/`
   - Ensure new features have test coverage
   - Run tests locally: `pytest`

4. **Test your changes**:
   ```shell
   # Run all tests
   pytest

   # Run specific test file
   pytest tests/test_minilinq.py
   ```
   For detailed testing instructions, database setup, and
   troubleshooting, see the [Testing Guide](docs/testing.md).

5. **Check type hints** (if modifying typed modules):
   ```shell
   mypy --install-types commcare_export/ tests/ migrations/
   ```

6. **Commit your changes** with clear messages:
   ```shell
   git add .
   git commit -m "Add feature: clear description of what you did"
   ```

7. **Push to your fork**:
   ```shell
   git push -u origin my-super-duper-feature
   ```

8. **Submit a pull request**:
   - Visit https://github.com/dimagi/commcare-export
   - Create a pull request from your branch to `master`
   - Fill out the PR description template
   - Wait for CI checks and code review

### Bug Fix Workflow

Follow the same workflow as features, with these notes:
- Branch name: `fix-issue-123` or `fix-bug-description`
- Commit message: "Fix bug where [description]"
- Include a test that reproduces the bug and verifies the fix
- Reference the issue number in your PR description

### Best Practices

- **Keep changes focused**: One feature or bug fix per PR
- **Write good commit messages**: Clear, concise, and descriptive
- **Update documentation**: If behavior changes, update relevant docs
- **Run tests frequently**: Catch issues early
- **Ask for help**: Open a draft PR if you need feedback


Building Executables
--------------------

CommCare Export can be compiled to standalone executables for Linux and
Windows using PyInstaller.

See [build_exe/README.md](../build_exe/README.md) for detailed
instructions.

Quick build:

```shell
cd build_exe
pip install -r requirements.txt
pyinstaller --clean commcare-export.spec
```


Database Migrations
-------------------

The project uses Alembic for database schema migrations (for checkpoint
tables).

See [migrations/README.md](../migrations/README.md) for migration
instructions.


CI/CD
-----

### GitHub Actions

The project uses GitHub Actions for continuous integration:

- **test.yml**: Runs tests on Python 3.9-3.13 across multiple platforms
- **release_actions.yml**: Builds executables on release


Debugging Tips
--------------

### Using pdb

```python
# Add to code where you want to debug
import pdb; pdb.set_trace()
```

### Verbose Output

```shell
# See detailed API requests and responses
commcare-export --query forms.xlsx --output-format markdown --verbose

# See compiled MiniLinq query
commcare-export --query forms.xlsx --dump-query
```

### Test with Small Data

```shell
# Limit date range for faster iteration
commcare-export --query forms.xlsx \
  --output-format markdown \
  --since 2023-01-01 --until 2023-01-02
```


Common Development Tasks
------------------------

### Adding a New Built-in Function

1. Add the function to `env.py` in the `BuiltInEnv` class
2. Add tests in `tests/test_minilinq.py`
3. Document in `docs/minilinq-reference.md`

### Adding a New Output Format

1. Create a new writer class in `writers.py` inheriting from `TableWriter`
2. Implement required methods: `write_table()`, etc.
3. Register in CLI (`cli.py`)
4. Add tests in `tests/test_writers.py`
5. Document in `docs/output-formats.md`

### Adding a New API Resource

1. Add resource handling in `commcare_minilinq.py`
2. Add pagination support if needed
3. Add integration tests
4. Document usage


Resources
---------

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [CommCare API Documentation](https://confluence.dimagi.com/display/commcarepublic/Data+APIs)


See Also
--------

- [Testing Guide](testing.md) - Running tests and test infrastructure
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contribution guidelines
- [Library Usage](library-usage.md) - Using commcare-export as a library
