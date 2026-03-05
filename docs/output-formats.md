Output Formats
--------------

Your MiniLinq may define multiple tables with headings in addition to their body rows by using `Emit`
expressions, or may simply return the results of a single query.

If your MiniLinq does not contain any `Emit` expressions, then the results of the expression will be
printed to standard output as pretty-printed JSON.

If your MiniLinq _does_ contain `Emit` expressions, then there are many formats available, selected
via the `--output-format <format>` option, and it can be directed to a file with the `--output <file>` command-line option.

 - `csv`: Each table will be a CSV file within a Zip archive.
 - `xls`: Each table will be a sheet in an old-format Excel spreadsheet.
 - `xlsx`: Each table will be a sheet in a new-format Excel spreadsheet.
 - `json`: The tables will each be a member of a JSON dictionary, printed to standard output
 - `markdown`: The tables will be streamed to standard output in Markdown format (very handy for debugging your queries)
 - `sql`: All data will be idempotently "upserted" into the SQL database you specify, including creating the needed tables and columns.


Dependencies
------------

Required dependencies will be automatically installed. Optional dependencies
for specific export formats can be installed as extras:

```shell
# To export "xlsx"
$ uv pip install "commcare-export[xlsx]"

# To export "xls"
$ uv pip install "commcare-export[xls]"

# To sync with a Postgres database
$ uv pip install "commcare-export[postgres]"

# To sync with a mysql database
$ uv pip install "commcare-export[mysql]"

# To sync with a database which uses odbc (e.g. mssql)
$ uv pip install "commcare-export[odbc]"

# To sync with another SQL database supported by SQLAlchemy
$ uv pip install "commcare-export[base_sql]"
# Then install the Python package for your database
```
