# Database Integration

*Part of [Technical Documentation](index.md)*

CommCare Export can export data directly to SQL databases, automatically
creating tables and columns as needed, and supporting incremental
updates via checkpoints.


Overview
--------

When using the SQL output format, CommCare Export will:

1. Connect to your database using SQLAlchemy
2. Automatically create tables that don't exist
3. Automatically add columns that don't exist
4. "Upsert" data (update existing rows, insert new ones)
5. Track export progress using checkpoints for incremental syncs


Connection Strings
------------------

CommCare Export uses SQLAlchemy's
[create_engine](http://docs.sqlalchemy.org/en/latest/core/engines.html),
which follows the [RFC-1738](https://www.ietf.org/rfc/rfc1738.txt) URL
format.

### PostgreSQL

```shell
# Basic format
postgresql://username:password@host:port/database

# With psycopg2 driver (recommended)
postgresql+psycopg2://username:password@localhost/mydatabase

# Example
commcare-export --query forms.xlsx --output-format sql \
  --output postgresql+psycopg2://scott:tiger@localhost/mydatabase
```

**Installation:**
```shell
uv pip install "commcare-export[postgres]"
```

### MySQL

```shell
# Basic format
mysql://username:password@host:port/database

# With pymysql driver (recommended)
mysql+pymysql://username:password@localhost/mydatabase

# Example
commcare-export --query forms.xlsx --output-format sql \
  --output mysql+pymysql://scott:tiger@localhost/mydatabase
```

**Installation:**
```shell
uv pip install "commcare-export[mysql]"
```

### MS SQL Server

```shell
# With pyodbc driver
mssql+pyodbc://username:password@host/database?driver=ODBC+Driver+17+for+SQL+Server

# Example
commcare-export --query forms.xlsx --output-format sql \
  --output 'mssql+pyodbc://SA:Password-123@localhost/mydatabase?driver=ODBC+Driver+17+for+SQL+Server'
```

**Installation:**
```shell
uv pip install "commcare-export[odbc]"
```

> [!NOTE]
> Requires the ODBC Driver for SQL Server to be installed on your
> system. See [Testing Guide](testing.md#odbc-driver-installation) for
> instructions.

### Other Databases

For other SQLAlchemy-supported databases:

```shell
# Install base SQL support
uv pip install "commcare-export[base_sql]"

# Then install your database's Python driver
uv pip install your-database-driver
```

Refer to
[SQLAlchemy's documentation](http://docs.sqlalchemy.org/en/latest/core/engines.html)
for connection string formats.


Schema Management
-----------------

### Automatic Table Creation

When you first run an export to a database, CommCare Export will
automatically create tables for each `Emit` expression in your query:

```shell
commcare-export --query forms.xlsx --output-format sql \
  --output postgresql://user:pass@localhost/mydb
```

If the `forms` table doesn't exist, it will be created with columns
matching your query.

### Automatic Column Addition

If you add new fields to your query, CommCare Export will automatically
add the corresponding columns to existing tables on the next run.

**Example:**

1. First run with columns: `patient_id`, `name`
2. Add `age` column to your Excel query
3. Next run automatically adds the `age` column to the database table

### Column Types

CommCare Export attempts to infer appropriate column types based on the
data:

- Text fields: `TEXT` or `VARCHAR`
- Numbers: `INTEGER` or `NUMERIC`
- Dates: `TIMESTAMP`
- Booleans: `BOOLEAN`

> [!NOTE]
> Type inference happens on first creation. If types are incorrect, drop
> the table and re-run to recreate it.


Upsert Behavior
---------------

CommCare Export performs "upserts" - it updates existing rows and
inserts new ones.

### Row Identification

Rows are identified by a composite key, typically including:

- For forms: `form_id` (or equivalent unique identifier)
- For cases: `case_id`

### Update vs Insert

- If a row with the same key exists: **UPDATE** - Replace all column
  values
- If no row with the key exists: **INSERT** - Add new row

This means:
- Re-running exports is safe (no duplicates)
- Updated data in CommCare HQ will update the database
- Deleted data in CommCare HQ will remain in the database (exports don't
  delete)


Checkpoints
-----------

Checkpoints enable incremental exports by tracking the last successfully
exported data.

### How Checkpoints Work

1. First run: Export all data, save checkpoint
2. Subsequent runs: Export only data since last checkpoint
3. Checkpoint updated after successful export

### Checkpoint Storage

Checkpoints are stored in the database itself, in tables like:

- `commcare_export_runs` - Track export runs
- Other checkpoint tables as needed

### Manual Date Control

You can override checkpoint behavior with command-line flags:

```shell
# Export data since a specific date
commcare-export --query forms.xlsx --output-format sql \
  --output postgresql://user:pass@localhost/mydb \
  --since 2023-01-01

# Export data in a date range
commcare-export --query forms.xlsx --output-format sql \
  --output postgresql://user:pass@localhost/mydb \
  --since 2023-01-01 --until 2023-12-31

# Start fresh (ignore checkpoint)
commcare-export --query forms.xlsx --output-format sql \
  --output postgresql://user:pass@localhost/mydb \
  --start-over
```

### Checkpoint Files

For non-SQL outputs, you can use checkpoint files:

```shell
commcare-export --query forms.xlsx --output-format xlsx \
  --output data.xlsx \
  --since 2023-01-01 \
  --checkpoint-file checkpoint.json
```

This saves checkpoint state to a JSON file for the next run.


Performance Considerations
--------------------------

### Index Creation

CommCare Export does not automatically create indexes. For better query
performance, create indexes on frequently queried columns:

```sql
-- PostgreSQL example
CREATE INDEX idx_patient_id ON forms (patient_id);
CREATE INDEX idx_received_on ON forms (received_on);
```

### Large Datasets

For very large exports:

1. **Use --since flag**: Only export recent data on subsequent runs
2. **Use checkpoints**: Enable automatic incremental exports
3. **Batch size**: The tool handles pagination automatically
4. **Database tuning**: Configure your database for bulk inserts

### Connection Pooling

For repeated exports, the tool creates a new connection each time. For
high-frequency exports, consider using a connection pooler like
PgBouncer (PostgreSQL).


Troubleshooting
---------------

### Connection Issues

**Problem:** Can't connect to database

**Solutions:**
- Verify database is running and accessible
- Check connection string format (quote special characters)
- Test connection string with a simple SQLAlchemy script
- Check firewall rules and network connectivity
- Verify username/password are correct

### Column Type Mismatches

**Problem:** Data doesn't fit in column

**Solutions:**
- Drop and recreate the table
- Manually alter the column type
- Update your query to transform data appropriately

### Permission Errors

**Problem:** User lacks permission to create tables/columns

**Solutions:**
- Grant appropriate permissions (CREATE, ALTER, INSERT, UPDATE)
- Use a database superuser for initial setup
- Pre-create tables with appropriate schema

### Duplicate Key Errors

**Problem:** Multiple rows with same key in a single export

**Solutions:**
- Check your query for duplicate data
- Ensure your data source filters are correct
- Review the MiniLinq query structure


Security Best Practices
-----------------------

1. **Use environment variables** for passwords:
   ```shell
   export DB_URL='postgresql://user:password@localhost/db'
   commcare-export --query forms.xlsx --output-format sql --output "$DB_URL"
   ```

2. **Use read-only credentials** when possible (for queries, not exports)

3. **Limit network access** to the database

4. **Use SSL/TLS connections** for remote databases:
   ```
   postgresql://user:pass@host/db?sslmode=require
   ```

5. **Avoid putting passwords in scripts** - use environment variables or
   credential files


Example Workflows
-----------------

### Initial Setup

```shell
# Install with PostgreSQL support
uv pip install "commcare-export[postgres]"

# First export (creates tables and exports all data)
commcare-export \
  --project myproject \
  --query forms.xlsx \
  --output-format sql \
  --output postgresql://user:pass@localhost/mydb
```

### Scheduled Incremental Updates

```shell
# Subsequent runs (exports only new data since last run)
commcare-export \
  --project myproject \
  --query forms.xlsx \
  --output-format sql \
  --output postgresql://user:pass@localhost/mydb

# Checkpoints are automatic - only new/modified data is exported
```

### Complete Refresh

```shell
# Drop the table
psql -c "DROP TABLE forms;" mydb

# Re-run the export
commcare-export \
  --project myproject \
  --query forms.xlsx \
  --output-format sql \
  --output postgresql://user:pass@localhost/mydb
```


See Also
--------

- [Output Formats](output-formats.md) - All available output formats
- [Scheduling](scheduling.md) - Automating regular exports
- [Testing Guide](testing.md) - Database testing and ODBC setup
- [User and Location Data](user-location-data.md) - Exporting organizational data
