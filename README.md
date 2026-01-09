CommCare Export
===============

https://github.com/dimagi/commcare-export

[![Build Status](https://github.com/dimagi/commcare-export/actions/workflows/test.yml/badge.svg)](https://github.com/dimagi/commcare-export/actions)
[![Test coverage](https://coveralls.io/repos/dimagi/commcare-export/badge.png?branch=master)](https://coveralls.io/r/dimagi/commcare-export)
[![PyPI version](https://badge.fury.io/py/commcare-export.svg)](https://badge.fury.io/py/commcare-export)

A command-line tool (and Python library) to generate customized exports from the [CommCare HQ](https://www.commcarehq.org) [REST API](https://wiki.commcarehq.org/display/commcarepublic/Data+APIs).


Features
--------

- **Flexible Queries**: Create custom exports using Excel or JSON query specifications
- **Multiple Output Formats**: Export to CSV, Excel, JSON, Markdown, or SQL databases
- **Incremental Exports**: Automatically track and export only new/modified data
- **Organization Data**: Export and join user and location data with forms and cases
- **Python Library**: Use as a library to integrate with your own applications
- **Scheduling Support**: Run automated exports on Windows, Linux, or Mac


Quick Start
-----------

### Installation

```shell
uv pip install commcare-export
```

### Basic Usage

```shell
# Export forms to Excel
commcare-export \
  --query examples/demo-registration.xlsx \
  --project YOUR_PROJECT \
  --output-format xlsx \
  --output data.xlsx

# Export to SQL database with incremental updates
commcare-export \
  --query examples/demo-registration.xlsx \
  --project YOUR_PROJECT \
  --output-format sql \
  --output postgresql://user:pass@localhost/dbname
```


Documentation
-------------

### For End Users

See the comprehensive [User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET) for:

- Installation and setup
- Creating queries with Excel
- Command-line usage
- Scheduling automated exports
- Common use cases and examples

### For Developers

See the [Technical Documentation](docs/index.md) for:

- [Python Library Usage](docs/library-usage.md) - Using commcare-export as a Python library
- [MiniLinq Reference](docs/minilinq-reference.md) - Query language documentation
- [Query Formats](docs/query-formats.md) - Excel and JSON query specifications
- [Output Formats](docs/output-formats.md) - Available output formats
- [Database Integration](docs/database-integration.md) - SQL database setup and usage
- [Development Guide](docs/development.md) - Contributing to the project


Examples
--------

Example query files are provided in the [examples/](examples/) directory for both Excel and JSON formats. All examples work with the CommCare Demo App available on the CommCare HQ Exchange.

Try them out:

```shell
commcare-export \
  --query examples/demo-deliveries.xlsx \
  --project YOUR_PROJECT \
  --output-format markdown
```


Contributing
------------

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- How to set up your development environment
- Code style guidelines
- Testing requirements
- Pull request process
- Release procedures


Community
---------

- **Changelog**: See [GitHub Releases](https://github.com/dimagi/commcare-export/releases) for version history
- **Issues**: Report bugs or request features on [GitHub Issues](https://github.com/dimagi/commcare-export/issues)
- **Questions**: Check the [User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET) or open an issue


Python Versions
---------------

CommCare Export is tested with Python 3.9, 3.10, 3.11, 3.12, and 3.13.


License
-------

MIT License - see [LICENSE](LICENSE) file for details.

Copyright (c) 2013-2026 Dimagi
