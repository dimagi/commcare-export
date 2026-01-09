Output Formats
==============

*Part of [Technical Documentation](index.md)*

CommCare Export supports multiple output formats for your exported data.
The format is selected via the `--output-format` option, and the
destination can be specified with `--output`.


Format Overview
---------------

Your MiniLinq query may define multiple tables with headings
(using `Emit` expressions), or may simply return the results of a
single query:

- **With `Emit` expressions**: Data will be written in the specified
    format with multiple tables
- **Without `Emit` expressions**: Results will be output as
    pretty-printed JSON to standard output


Available Formats
-----------------

### CSV

Each table will be a CSV file within a Zip archive.

**Usage:**
```shell
commcare-export --query my-query.xlsx --output-format csv --output data.zip
```

**Characteristics:**
- Multiple tables = multiple CSV files in a single ZIP
- Compatible with all spreadsheet applications
- Good for sharing data with non-technical users
- File size can be smaller than Excel formats

**When to use:**
- Exporting for analysis in R, Python, or other data tools
- Sharing data with users who don't have Excel
- When file size is a concern

### XLS

Each table will be a sheet in an old-format Excel spreadsheet (.xls).

**Usage:**
```shell
commcare-export --query my-query.xlsx --output-format xls --output data.xls
```

**Requires:** `uv pip install "commcare-export[xls]"`

**Characteristics:**
- Legacy Excel format (Excel 97-2003)
- Row limit: 65,536 rows per sheet
- Column limit: 256 columns
- Smaller file size than XLSX

**When to use:**
- Compatibility with very old Excel versions
- When file size is critical
- **Not recommended** for new projects - use XLSX instead

### XLSX

Each table will be a sheet in a new-format Excel spreadsheet (.xlsx).

**Usage:**
```shell
commcare-export --query my-query.xlsx --output-format xlsx --output data.xlsx
```

**Requires:** `uv pip install "commcare-export[xlsx]"`

**Characteristics:**
- Modern Excel format (Excel 2007+)
- Row limit: 1,048,576 rows per sheet
- Column limit: 16,384 columns
- Widely compatible

**When to use:**
- Sharing with Excel users
- When you need multiple related tables in one file
- Large datasets (within row limits)
- **Recommended** Excel format for most use cases

### JSON

The tables will each be a member of a JSON dictionary, printed to
standard output.

**Usage:**
```shell
commcare-export --query my-query.xlsx --output-format json > data.json
```

**Characteristics:**
- Machine-readable format
- Preserves data types precisely
- Can be piped to other tools
- No external dependencies required

**Output structure:**
```json
{
  "table1": [
    {"col1": "value1", "col2": "value2"},
    {"col1": "value3", "col2": "value4"}
  ],
  "table2": [
    {"col1": "value5", "col2": "value6"}
  ]
}
```

**When to use:**
- Feeding data to another application
- Programmatic data processing
- When you need to preserve data types
- Integration with web services or APIs

### Markdown

The tables will be streamed to standard output in Markdown format.

**Usage:**
```shell
commcare-export --query my-query.xlsx --output-format markdown
```

**Characteristics:**
- Human-readable text format
- Displays nicely in terminals
- Can be pasted into documentation
- Very fast (streaming output)
- No file size limits

**Example output:**
```markdown
| Patient ID | Name | Visit Date |
|------------|------|------------|
| 001        | John | 2023-01-15 |
| 002        | Jane | 2023-01-16 |
```

**When to use:**
- **Debugging queries** (highly recommended)
- Quick data inspection
- Creating documentation
- Terminal-based workflows

### SQL

All data will be idempotently "upserted" into the SQL database you
specify, including creating the needed tables and columns.

**Usage:**
```shell
# PostgreSQL
commcare-export --query my-query.xlsx --output-format sql \
  --output postgresql://user:password@localhost/dbname

# MySQL
commcare-export --query my-query.xlsx --output-format sql \
  --output mysql+pymysql://user:password@localhost/dbname

# MS SQL Server
commcare-export --query my-query.xlsx --output-format sql \
  --output 'mssql+pyodbc://user:password@localhost/dbname?driver=ODBC+Driver+17+for+SQL+Server'
```

**Characteristics:**
- Automatically creates tables and columns
- Upserts data (updates existing, inserts new)
- Supports incremental exports via checkpoints
- Multiple database backends supported

**When to use:**
- Building a data warehouse
- Integration with BI tools (Tableau, PowerBI, etc.)
- Scheduled/recurring exports
- Large datasets requiring database performance
- When you need SQL query capabilities

For complete details, see
[Database Integration](database-integration.md).


Connection String Formats
-------------------------

CommCare Export uses SQLAlchemy's
[create_engine](http://docs.sqlalchemy.org/en/latest/core/engines.html),
which is based on [RFC-1738](https://www.ietf.org/rfc/rfc1738.txt).

### PostgreSQL

```
postgresql://username:password@localhost/database_name
postgresql+psycopg2://username:password@localhost/database_name
```

**Requires:** `uv pip install "commcare-export[postgres]"`

### MySQL

```
mysql://username:password@localhost/database_name
mysql+pymysql://username:password@localhost/database_name
```

**Requires:** `uv pip install "commcare-export[mysql]"`

### MS SQL Server

```
mssql+pyodbc://username:password@localhost/database_name?driver=ODBC+Driver+17+for+SQL+Server
```

**Requires:**
- `uv pip install "commcare-export[odbc]"`
- ODBC Driver for SQL Server (see
  [Testing Guide](testing.md#odbc-driver-installation))

### Other Databases

For other SQLAlchemy-supported databases:

```shell
uv pip install "commcare-export[base_sql]"
# Then install your database's Python driver
```


Choosing an Output Format
-------------------------

| Use Case                 | Recommended Format | Alternative  |
|--------------------------|--------------------|--------------|
| Debugging queries        | Markdown           | JSON         |
| Ad-hoc analysis          | XLSX               | CSV          |
| Sharing with Excel users | XLSX               | CSV          |
| Data warehouse/BI tools  | SQL                | CSV + import |
| Programmatic processing  | JSON               | CSV          |
| Large recurring exports  | SQL                | CSV          |
| Web service integration  | JSON               | -            |
| Documentation/reports    | Markdown           | XLSX         |


Multiple Runs and Incremental Updates
-------------------------------------

### File-based Formats (CSV, Excel, JSON, Markdown)

- Each run completely replaces the previous output
- No incremental update capability
- Use `--since` flag to control date ranges

### SQL Format

- Supports incremental updates via checkpoints
- Automatically tracks last successful export
- Upserts data (no duplicates)
- See [Database Integration](database-integration.md#checkpoints) for
  details


Performance Considerations
--------------------------

### Fastest to Slowest (for large datasets)

1. **SQL** - Direct database write, can handle millions of rows
2. **JSON** - Streaming output, minimal processing
3. **Markdown** - Streaming output, text formatting overhead
4. **CSV** - Compression overhead
5. **XLSX** - Excel file format has higher overhead
6. **XLS** - Legacy format, slowest and most limited

### Memory Usage

- **Streaming formats** (Markdown, SQL): Low memory footprint
- **Buffered formats** (CSV, Excel, JSON): Entire dataset loaded in
  memory
- For very large exports, use SQL format


See Also
--------

- [Database Integration](database-integration.md) - Detailed SQL
  database documentation
- [Query Formats](query-formats.md) - Creating queries
- [Command-Line Usage](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/) -
  Full CLI reference
