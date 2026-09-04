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
| `delta`    | Idempotent "upsert" into Delta Lake tables in a local directory or object storage, creating tables and columns as needed |


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

# Delta Lake
uv pip install "commcare-export[delta]"
```

For database connection string formats, see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Generating-Database-Connection-Strings).


Delta Lake Output
-----------------

`--output-format delta` writes each table as a
[Delta Lake](https://delta.io) table under the base URI given by
`--output`, which can be a local directory or an object storage URI
such as `az://container/path` or `s3://bucket/path`. Delta output
requires a Python installation with the `delta` extra; the pre-built
executable does not include it. Storage
credentials are read from the environment using the storage provider's
standard variables (see the
[delta-rs storage documentation](https://delta-io.github.io/delta-rs/usage/loading-table/)),
so they never appear on the command line.

Rows are upserted by their `id` column, so every table must include
one. Rows without an `id` value are skipped with a warning and are not
retried by later incremental runs. Table names may not contain path or
URI punctuation (`/ \ % ? # : [ ] ^ |` or `..`), and column names may
not contain backticks. Columns with a declared data type
are written with the matching Delta type; all other columns are written
as strings. A column's type is fixed when it is first written, so
changing a column's declared type later requires recreating the table.
`datetime` values are stored as UTC timestamps, `json` values are
stored as JSON strings, `boolean` columns accept `true`/`false`,
`t`/`f` and `1`/`0` in any case, and floats in `integer` columns are
rounded.

Delta output has no database in which to record checkpoints, so pass
`--checkpoint-database-url` (any SQLAlchemy URL, e.g.
`sqlite:///checkpoints.db`) to enable incremental exports. Without it,
each run exports from the beginning.

Use a separate checkpoint database, or a distinct `--checkpoint-key`,
for each destination. Checkpoints identify the query and project but
not the destination, so a checkpoint database shared across
destinations makes a second destination resume where the first left off
and skip its older records.

A first export appends rows in chunks of up to 100,000; later runs
merge updates in chunks of the same size. A run that makes more than
one commit to a table compacts that table's files when it finishes.
Long-lived destinations that receive small scheduled runs still
benefit from a periodic `OPTIMIZE` on your platform.

Delta runs record their checkpoint only after the whole export
succeeds. If a run fails partway, nothing is checkpointed; the next
run re-fetches the same window and the merge reapplies it.

Delta keeps old file versions when data changes, so tables that are
updated on a schedule accumulate historical files. Reclaim that space
periodically with your platform's `VACUUM` command; the usual default
keeps seven days of history, which preserves time travel over recent
versions.

Run one export at a time per destination. Concurrent writers to the
same table are safe on Azure, Google Cloud Storage, and AWS S3, where
delta-rs commits with atomic conditional writes; S3-compatible stores
that lack conditional-write support are not safe for concurrent
writers.

```shell
commcare-export \
    --query my-query.xlsx \
    --project YOUR_PROJECT \
    --output-format delta \
    --output az://analytics/commcare \
    --checkpoint-database-url sqlite:///checkpoints.db
```


See Also
--------

- [Query Formats](query-formats.md) - Creating queries
- [MiniLinq Reference](minilinq-reference.md) - The `Emit` expression
