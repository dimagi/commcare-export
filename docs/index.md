CommCare Data Export Tool - Technical Documentation
===================================================

This documentation is for developers who want to use `commcare-export`
as a Python library, contribute to the project, or understand its
internals.

For end-user documentation about installing and using the command-line
tool, see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET).


For Library Users
-----------------

- [Python Library Usage](library-usage.md) - Using `commcare-export` as
  a Python library
- [MiniLinq Reference](minilinq-reference.md) - Query language syntax
  and built-in functions


Query and Output
----------------

- [Query Formats](query-formats.md) - Excel and JSON query formats
- [Output Formats](output-formats.md) - CSV, Excel, JSON, SQL, and
  Markdown outputs
- [User and Location Data](user-location-data.md) - Exporting
  organization data
- [Command-line Usage](cli-usage.md) - CLI reference and logging
- [Scheduling](scheduling.md) - Running the DET on a schedule


Development
-----------

- [Contributing Guide](../CONTRIBUTING.md) - How to contribute,
  coding style, and release process
- [Testing Guide](testing.md) - Running tests with multiple databases
- [Database Migrations](../migrations/README.md) - Using Alembic
  migrations
