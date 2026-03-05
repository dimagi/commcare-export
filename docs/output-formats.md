Output Formats
==============

For end-user documentation on exporting data (including database
connection strings, checkpoints, and detailed usage), see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Exporting-Data).


Format Summary
--------------

If your query does not contain any `Emit` expressions, results are
printed to standard output as pretty-printed JSON.

If your query _does_ contain `Emit` expressions, the format is selected
via `--output-format <format>` and the destination via `--output <file>`:

| Format     | Description                                                      |
|------------|------------------------------------------------------------------|
| `csv`      | Each table as a CSV file within a Zip archive                    |
| `xls`      | Each table as a sheet in an old-format Excel spreadsheet         |
| `xlsx`     | Each table as a sheet in a new-format Excel spreadsheet          |
| `json`     | Tables as members of a JSON dictionary, printed to stdout        |
| `markdown` | Tables streamed to stdout in Markdown format (handy for debugging) |
| `sql`      | Idempotent "upsert" into a SQL database, creating tables and columns as needed |


Optional Dependencies
---------------------

Required dependencies are installed automatically. Install extras for
specific output formats:

```shell
# Excel formats
uv pip install "commcare-export[xlsx]"
uv pip install "commcare-export[xls]"

# Database backends
uv pip install "commcare-export[postgres]"
uv pip install "commcare-export[mysql]"
uv pip install "commcare-export[odbc]"       # MS SQL Server
uv pip install "commcare-export[base_sql]"   # Other SQLAlchemy databases
```

For database connection string formats, see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Generating-Database-Connection-Strings).


See Also
--------

- [Query Formats](query-formats.md) - Creating queries
- [MiniLinq Reference](minilinq-reference.md) - The `Emit` expression
