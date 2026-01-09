CommCare Export Technical Documentation
=======================================

Welcome to the CommCare Export technical documentation. This
documentation is intended for developers who want to use
commcare-export as a Python library, contribute to the project, or
understand its internals.

For end-user documentation about installing and using the command-line
tool, please see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET).


Quick Links
-----------

- [Python Library Usage](library-usage.md) - Get started using
  commcare-export as a library
- [MiniLinq Reference](minilinq-reference.md) - Query language
  documentation
- [Contributing Guide](../CONTRIBUTING.md) - How to contribute to the
  project


For Library Users
-----------------

- [Python Library Usage](library-usage.md) - Using commcare-export as a
  Python library
- [MiniLinq Reference](minilinq-reference.md) - Query language syntax
  and built-in functions
- [API Client](library-usage.md#commcare-hq-api-client) - CommCare HQ
  REST API client usage


Query Specifications
--------------------

- [Query Formats](query-formats.md) - Excel and JSON query formats
- [Output Formats](output-formats.md) - CSV, Excel, JSON, SQL, and
  Markdown outputs


Advanced Topics
---------------

- [Database Integration](database-integration.md) - SQL database
  connections and syncing
- [User and Location Data](user-location-data.md) - Exporting
  organization data
- [Scheduling](scheduling.md) - Running DET on a schedule


Development
-----------

- [Development Guide](development.md) - Setting up development
  environment
- [Testing Guide](testing.md) - Running tests with multiple databases
- [Building Executables](../build_exe/README.md) - Creating standalone
  binaries
- [Database Migrations](../migrations/README.md) - Using Alembic
  migrations


Contributing
------------

See [CONTRIBUTING.md](../CONTRIBUTING.md) for information about:

- Setting up your development environment
- Running tests
- Submitting pull requests
- Release process
