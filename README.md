CommCare Data Export Tool
========================

https://github.com/dimagi/commcare-export

[![Build Status](https://github.com/dimagi/commcare-export/actions/workflows/test.yml/badge.svg)](https://github.com/dimagi/commcare-export/actions)
[![Test coverage](https://coveralls.io/repos/dimagi/commcare-export/badge.png?branch=master)](https://coveralls.io/r/dimagi/commcare-export)
[![PyPI version](https://badge.fury.io/py/commcare-export.svg)](https://badge.fury.io/py/commcare-export)

A command-line tool (and Python library) to generate customized exports
from the [CommCare HQ](https://www.commcarehq.org)
[REST API](https://wiki.commcarehq.org/display/commcarepublic/Data+APIs).


Quick Start
-----------

### Installation

```shell
uv pip install commcare-export
```

### Basic Usage

```shell
# Export forms to Markdown (useful for testing)
commcare-export \
    --query examples/demo-registration.xlsx \
    --project YOUR_PROJECT \
    --output-format markdown

# Export to a SQL database with incremental updates
commcare-export \
    --query examples/demo-registration.xlsx \
    --project YOUR_PROJECT \
    --output-format sql \
    --output postgresql://user:pass@localhost/dbname
```

Example query files are provided in the [examples/](examples/) directory
for both Excel and JSON formats.


Documentation
-------------

### For Users

See the [User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET)
for installation, creating queries, command-line usage, scheduling, and
common use cases.

### For Developers

See the [Technical Documentation](docs/index.md) for:

- [Python Library Usage](docs/library-usage.md) - Using `commcare-export` as a Python library
- [MiniLinq Reference](docs/minilinq-reference.md) - Query language documentation
- [Query Formats](docs/query-formats.md) - Excel and JSON query specifications
- [Output Formats](docs/output-formats.md) - Available output formats and dependencies
- [User and Location Data](docs/user-location-data.md) - Exporting organization data
- [Command-line Usage](docs/cli-usage.md) - CLI reference
- [Scheduling](docs/scheduling.md) - Running DET on a schedule


Contributing
------------

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for
how to set up your development environment, coding style guidelines,
testing, and the release process.

- [Testing Guide](docs/testing.md)
- [Changelog](https://github.com/dimagi/commcare-export/releases)


Python Versions
---------------

Tested with Python 3.10, 3.11, 3.12, and 3.13.


License
-------

MIT License - see [LICENSE](LICENSE) for details.
