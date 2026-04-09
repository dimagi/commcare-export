# SQL Writer Memory Optimization

## Problem

When exporting millions of rows to a SQL database, `SqlTableWriter` in
`commcare_export/writers.py` uses excessive memory because:

1. **Per-row schema checking**: `make_table_compatible()` is called for every
   row, creating `MigrationContext` and `Operations` objects each time. On
   schema changes it calls `metadata.clear()` and re-reflects the table,
   creating churn in SQLAlchemy's `MetaData` object graph.

2. **Per-row SQL compilation**: `upsert()` compiles a new `INSERT` (and
   potentially `UPDATE`) statement object for every row.

3. **No commit batching**: The entire export runs without intermediate commits,
   so the database driver may buffer transaction state for the full duration.

## Design

### 1. Limit `make_table_compatible()` to the first N rows

**Constant**: `SCHEMA_CHECK_ROWS = 10`

In `write_table()`, only call `make_table_compatible()` for rows where
`i < SCHEMA_CHECK_ROWS`. After that, assume the schema is stable.

This also addresses SQLAlchemy `MetaData` object growth: the
`metadata.clear()` / `get_table()` cycle that causes MetaData churn only runs
inside `make_table_compatible()`. Once we stop calling it after row 10, the
MetaData object holds only the stable reflected table and no further
MigrationContext/Operations objects are allocated.

**Logging**: After the schema-check phase completes (at row `SCHEMA_CHECK_ROWS`
or when all rows have been consumed, whichever comes first), log a message at
`DEBUG` level confirming that schema checks are complete and listing the final
column set.

#### Error handling

After row 10, a row may contain a value that is incompatible with the current
column type, or a column that doesn't exist in the table. When a batch insert
fails:

1. Check whether the failure is due to a schema mismatch (missing column or
   type incompatibility).
2. If so, call `make_table_compatible()` for the failing row, then retry the
   entire batch. Only do this **once per batch** -- if the retry also fails,
   raise the original exception.
3. If the failure is not schema-related, raise immediately.

This keeps the common path fast while still handling late schema evolution.

### 2. Batch writes and commits

**Constant**: `BATCH_SIZE = 1000`

Replace the current row-at-a-time loop with batched processing:

```
accumulate rows into a batch (list of row dicts)
when batch is full (or rows are exhausted):
    try:
        bulk upsert the batch
    except schema error:
        run make_table_compatible on the failing row
        retry the batch once
    commit
```

#### Bulk upsert strategy

The current `upsert()` method does `INSERT`, then falls back to `UPDATE` on
`IntegrityError`. For batched operation, use **dialect-specific bulk upsert**:

- **PostgreSQL**: Use `sqlalchemy.dialects.postgresql.insert` with
  `on_conflict_do_update()` on the `id` primary key. Pass the full batch to
  `connection.execute(statement, batch_list)`.

- **MySQL**: Use `sqlalchemy.dialects.mysql.insert` with
  `on_duplicate_key_update()`. Pass the full batch to
  `connection.execute(statement, batch_list)`.

- **MSSQL**: Use a `MERGE` statement via raw SQL, or fall back to row-by-row
  upsert within the batch. MSSQL doesn't have a clean SQLAlchemy upsert API.

- **Other dialects** (Oracle, etc.): Fall back to row-by-row `upsert()` within
  the batch, same as current behavior. The commit-per-batch improvement still
  applies.

Implement a method `bulk_upsert(table, batch)` that dispatches on
`self.is_postgres` / `self.is_mysql` / `self.is_mssql` and falls back to
row-by-row for unsupported dialects.

#### Commits

Call `self.connection.execute(text("COMMIT"))` (or use the connection's
transaction API) after each batch. This bounds the transaction size and lets the
database release resources.

#### Filtering None values

The current `upsert()` strips `None` values from `row_dict` so that columns
that don't yet exist aren't included. For bulk inserts, all rows in a batch must
have the **same set of keys**. To handle this:

- After schema checking is complete (row 10+), build the batch using a stable
  set of column names (the headings from `table_spec.headings`).
- Include `None` values as-is -- the columns exist by this point (all columns
  are nullable).
- During the schema-check phase (rows 0-9), continue using row-by-row
  `upsert()` with None-stripping, since columns may not exist yet.

### 3. Revised `write_table()` flow

```python
def write_table(self, table_spec):
    table_name = table_spec.name
    headings = table_spec.headings
    data_type_dict = dict(zip_longest(headings, table_spec.data_types))

    table = None
    batch = []

    for i, row in enumerate(table_spec.rows):
        row_dict = dict(zip(headings, row))

        if i == 0:
            table = self.get_table(table_name)
            if table is None:
                table = self.create_table(table_name, row_dict, data_type_dict)

        if i < SCHEMA_CHECK_ROWS:
            # Schema-check phase: row-by-row with full compatibility checks
            table = self.make_table_compatible(table, row_dict, data_type_dict)
            self.upsert(table, row_dict)
        else:
            # Batched phase
            batch.append(row_dict)
            if len(batch) >= BATCH_SIZE:
                self._flush_batch(table, batch)
                batch = []

    # Flush any remaining rows
    if batch:
        self._flush_batch(table, batch)

    # Commit any remaining schema-check-phase rows
    if table is not None:
        self._commit()


def _flush_batch(self, table, batch):
    try:
        self.bulk_upsert(table, batch)
    except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.ProgrammingError):
        # Likely a schema mismatch; try to fix and retry once
        for row_dict in batch:
            table = self.make_table_compatible(table, row_dict, ...)
        self.bulk_upsert(table, batch)  # retry; raise on second failure
    self._commit()
```

### 4. What this does NOT change

- **API fetching**: Already lazy/paginated. No changes needed.
- **minilinq pipeline**: Already uses generators. No changes needed.
- **`JValueTableWriter`**: Used for JSON output, not SQL. Out of scope.
- **`StreamingMarkdownTableWriter`**: Used for terminal display. Out of scope.
- **The `upsert()` method**: Kept as-is for the schema-check phase and for
  dialect fallback within batches.

## Files to modify

- `commcare_export/writers.py`: All changes are in `SqlTableWriter`.
  - Add constants `SCHEMA_CHECK_ROWS` and `BATCH_SIZE`.
  - Add `bulk_upsert()` method.
  - Add `_flush_batch()` method.
  - Add `_commit()` helper.
  - Rewrite `write_table()` as described above.

## Testing

- Existing tests in `tests/test_writers.py` must continue to pass (they
  exercise the full write_table path with small row counts that stay within the
  schema-check phase).
- Add a test that writes > `SCHEMA_CHECK_ROWS` rows to verify the batched
  path is exercised.
- Add a test that introduces a new column after row 10 to verify the
  schema-mismatch retry logic.
- Test with PostgreSQL and MySQL dialects (at minimum) to verify bulk upsert.
