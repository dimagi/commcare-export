# SQLAlchemy 2.0 Upgrade

## Motivation

The current branch (`nh/write_table`) uses SQLAlchemy 1.4 with
`sqlalchemy~=1.4` pinned in `pyproject.toml`. Transaction management
relies on a raw `COMMIT` SQL statement (`writers.py:613`), which is
unstable on Postgres with large row counts. SQLAlchemy 2.0 provides
explicit transaction scoping that will fix this.


## Current State

### Transaction model in `SqlTableWriter`

`SqlMixin.__enter__` opens a bare connection:

```python
self.connection = self.engine.connect()
```

Under SQLAlchemy 1.4's default "autocommit" behavior, each
`connection.execute(insert)` auto-commits. When an explicit commit is
needed (e.g. after `bulk_upsert`), the code issues:

```python
self.connection.execute(sqlalchemy.text('COMMIT'))
```

This raw COMMIT is the root cause of the Postgres instability: it
bypasses SQLAlchemy's connection state tracking, so the connection may
or may not be inside a transaction depending on timing and driver
behavior.

### Deprecated patterns in use

| Pattern                        | Location(s)       |
|--------------------------------|-------------------|
| `MetaData(bind=connection)`    | `writers.py:338`  |
| `MetaData(bind=op.get_bind())` | 4 migration files |
| `MetaData(bind=writer.engine)` | `test_cli.py:893` |
| `Table(..., autoload=True)`    | 3 migration files |
| `engine.execute(...)`          | `tests/utils.py:17`, `test_cli.py:533,615,650,849,909` |
| `conn.execute('raw string')`   | `conftest.py:36,39,50,53`, `test_writers.py:106-108,140-145` |
| `declarative_base()` from `sqlalchemy.ext.declarative` | `checkpoint.py:10,18` |

### Session management in `CheckpointManager`

Uses a manual `session_scope` context manager (`checkpoint.py:70-83`)
with `sessionmaker`. This is compatible with 2.0 but can be simplified.

### Alembic `env.py`

`env.py:10` accepts either a connection (from `cfg.attributes`) or
creates an engine. Line 19 calls `.connect()` on whatever it gets.
When `checkpoint.py:207` passes a `Connection` via
`cfg.attributes['connection']`, calling `.connect()` on a `Connection`
works in 1.4 (returns a "branched" connection) but the semantics change
in 2.0. This needs attention.


## Design

### Phase 1: Mechanical 2.0 compatibility

These changes make the code run on SQLAlchemy 2.0 without changing
behavior. They should be done in a single commit so the version bump
and API fixes are atomic.

**1a. Bump the version pin**

In `pyproject.toml`, change `sqlalchemy~=1.4` to `sqlalchemy~=2.0`.

**1b. Remove `MetaData(bind=...)`**

SQLAlchemy 2.0 removes the `bind` parameter from `MetaData`.

`writers.py` -- Replace the `metadata` property. Instead of binding
metadata to a connection, create unbound metadata and pass the
connection explicitly where needed:

```python
@property
def metadata(self):
    if self._metadata is None:
        self._metadata = sqlalchemy.MetaData()
    return self._metadata
```

The only consumer is `get_table`, which already passes
`autoload_with=self.connection`. Since `autoload_with` doesn't require
bound metadata, no further changes are needed there.

Migration files -- Replace `sa.MetaData(bind=op.get_bind())` with
`sa.MetaData()` and change `autoload=True` to
`autoload_with=op.get_bind()`:

- `c36489c5a628`: `meta = sa.MetaData()` then
  `meta.reflect(bind=op.get_bind())`
- `d3ce9dc9907a`: `meta = sa.MetaData()` then
  `sa.Table('commcare_export_runs', meta, autoload_with=op.get_bind())`
- `29c27e7e2bf6`: same as above
- `9945abb4ec70`: same as above

`test_cli.py:893` -- Replace `MetaData(bind=writer.engine)` with
`MetaData()`.

**1c. Replace `engine.execute()` with `connection.execute()`**

`engine.execute()` is removed in 2.0. Every call site needs to use
`with engine.connect() as conn:` instead.

- `tests/utils.py:17` -- `SqlWriterWithTearDown.tear_down()`:
  ```python
  def tear_down(self):
      with self.engine.connect() as conn:
          for table in self.tables:
              conn.execute(sqlalchemy.text(f'DROP TABLE "{table}"'))
              conn.commit()
      self.tables = set()
  ```

- `test_cli.py:533` (`_check_data`) -- wrap in
  `with writer.engine.connect() as conn:` and use `sqlalchemy.text()`.

- `test_cli.py:615,650` -- same pattern: open a connection, use
  `text()` with named params.

- `test_cli.py:849` -- already uses `sqlalchemy.text()` but calls
  `engine.execute()`; move into connection context.

- `test_cli.py:909` -- same.

**1d. Wrap raw SQL strings in `text()`**

All `conn.execute('raw string')` calls must become
`conn.execute(text('raw string'))`.

- `conftest.py:36,39,50,53` -- wrap all four calls.
- `test_writers.py:106-108,140-145` -- wrap the `SELECT` statements.

**1e. Move `declarative_base` import**

`checkpoint.py:10` imports from `sqlalchemy.ext.declarative`, which is
deprecated. Change to:

```python
from sqlalchemy.orm import DeclarativeBase
```

And replace `Base = declarative_base()` with:

```python
class Base(DeclarativeBase):
    pass
```

**1f. Fix `env.py` connection handling**

When a `Connection` is passed via `cfg.attributes`, don't call
`.connect()` on it (2.0 no longer supports "branching" connections
this way). Instead, use the connection directly:

```python
def run_migrations_online():
    connectable = config.attributes.get('connection', None)

    if connectable is None:
        cmd_line_url = context.get_x_argument(as_dictionary=True).get('url')
        if cmd_line_url:
            connectable = create_engine(cmd_line_url)
        else:
            raise Exception("No connection URL. Use '-x url=<url>'")

    if isinstance(connectable, Connection):
        _run_migrations(connectable)
    else:
        with connectable.connect() as connection:
            _run_migrations(connection)


def _run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()
```

**1g. Remove `sqlalchemy-migrate` dependency**

`pyproject.toml` lists `sqlalchemy-migrate` but nothing in the
codebase imports it. Remove it. (It doesn't support SQLAlchemy 2.0
anyway.)


### Phase 2: Explicit transaction management

This is the key behavioral change. Replace the raw `COMMIT` hack with
SQLAlchemy 2.0's explicit transaction API.

**2a. Use `connection.begin()` in `SqlMixin`**

Change `__enter__`/`__exit__` to manage an explicit transaction:

```python
def __enter__(self):
    self.connection = self.engine.connect()
    self.transaction = self.connection.begin()
    return self

def __exit__(self, exc_type, exc_val, exc_tb):
    if exc_type is None:
        self.transaction.commit()
    else:
        self.transaction.rollback()
    self.connection.close()
```

This means every `with writer:` block is a single transaction that
commits on clean exit and rolls back on exception.

**2b. Replace `_commit()` with `_flush()`**

In `write_table`, the current `_commit()` calls serve two purposes:
1. After the schema-check phase (line 710): persist schema changes and
   initial rows before switching to batch mode.
2. After each batch flush (line 674): persist a batch of rows.
3. At the end if all rows were in schema-check phase (line 728).

With 2.0's "begin once" connection model, we need intermediate commits.
Replace `_commit()` with a method that commits the current transaction
and starts a new one:

```python
def _flush(self):
    self.transaction.commit()
    self.transaction = self.connection.begin()
```

This gives us the same semantics -- each batch is independently
committed -- but uses SQLAlchemy's transaction API instead of raw SQL.

**2c. Update `_flush_batch` and `write_table`**

Replace `self._commit()` calls with `self._flush()`. The semantics
are identical: after each batch, we commit what we have and start fresh.

The `__exit__` method handles the final commit (or rollback on error),
so the last batch doesn't need a special case.

Wait -- actually there's a subtlety. If `_flush_batch` commits and
then `__exit__` also commits, we'd double-commit. We need the
`__exit__` to handle the case where there's an active transaction with
uncommitted work (the final batch or schema-check-only case).

Better approach: `__exit__` should always commit/rollback whatever is
pending:

```python
def __exit__(self, exc_type, exc_val, exc_tb):
    try:
        if exc_type is None:
            self.transaction.commit()
        else:
            self.transaction.rollback()
    finally:
        self.connection.close()
```

And `_flush()` commits + begins a new transaction. This way:
- After each `_flush()`, a new transaction is active.
- `__exit__` commits the final transaction.
- On exception, `__exit__` rolls back the current transaction.

**2d. Handle the upsert retry in `_flush_batch`**

Currently `_flush_batch` catches errors from `bulk_upsert`, fixes the
schema, and retries. After a failed `bulk_upsert`, the transaction is
in an error state (especially on Postgres). We need to roll back and
begin a new transaction before retrying:

```python
def _flush_batch(self, table, batch, data_type_dict):
    try:
        self.bulk_upsert(table, batch)
    except (...):
        self.transaction.rollback()
        self.transaction = self.connection.begin()
        for row_dict in batch:
            table = self.make_table_compatible(
                table, row_dict, data_type_dict,
            )
        self.bulk_upsert(table, batch)
    self._flush()
```

**2e. Handle schema-check upserts**

During the schema-check phase, `upsert()` is called row-by-row. Each
`upsert` does an INSERT, and on `IntegrityError`, falls back to
UPDATE. The `IntegrityError` puts the transaction in an error state
on Postgres. We need savepoints:

```python
def upsert(self, table, row_dict):
    row_dict = {k: v for k, v in row_dict.items() if v is not None}
    savepoint = self.connection.begin_nested()
    try:
        self.connection.execute(table.insert().values(**row_dict))
        savepoint.commit()
    except sqlalchemy.exc.IntegrityError:
        savepoint.rollback()
        self.connection.execute(
            table.update()
            .where(table.c.id == row_dict['id'])
            .values(**row_dict)
        )
```

`begin_nested()` creates a SAVEPOINT, so the `IntegrityError` only
rolls back to the savepoint, not the whole transaction.


### Phase 3: Remove `sqlalchemy-migrate`

Simply remove `'sqlalchemy-migrate'` from the `dependencies` list in
`pyproject.toml`. Nothing imports it.


### Phase 4: Optional modernization (not required)

These are compatible improvements that could be done later:

- **`metadata` property simplification**: With bound metadata removed,
  the `metadata` property (`writers.py:327-339`) loses all its
  connection-validity checks and collapses to a simple lazy-init of
  `MetaData()`. The `get_table` method already uses
  `autoload_with=self.connection`, which is the 2.0 way.

- **`CheckpointManager` doesn't need `SqlMixin`'s connection
  lifecycle**: `CheckpointManager` inherits `__enter__`/`__exit__`
  from `SqlMixin`, but never uses `self.connection` for real work --
  it uses `Session` for ORM operations and `engine.begin()` for
  migrations. The only use of `manager.connection` is in test teardown
  (`test_checkpointmanager.py:30-36`). This is an inheritance smell,
  but a larger refactor than the upgrade warrants.

- **DDL inside transactions**: Under Phase 2's explicit transactions,
  `make_table_compatible` and `create_table` (which use
  `MigrationContext.configure(self.connection)`) will run DDL inside
  the active transaction. On Postgres, DDL is transactional, so a
  failed schema change rolls back cleanly. This is a free improvement.

- **Session `session.query()` to `select()` style**: The 1.x query API
  (`session.query(Checkpoint).filter_by(...)`) still works in 2.0 but
  is "legacy". Could migrate to `session.execute(select(Checkpoint).where(...))`.
  Low priority since the current code works.

- **`session_scope` to `Session` as context manager**: SQLAlchemy 2.0's
  `Session` can be used directly as a context manager with
  `with Session() as session:` (handles commit/rollback). This would
  let us remove the manual `session_scope` function. However, the
  current code is clear and explicit, so this is optional.


## Commit plan

Following the project's CLAUDE.md instruction to separate moves/renames
from code changes:

1. **Remove `sqlalchemy-migrate` dependency** -- pyproject.toml only
2. **Upgrade SQLAlchemy 1.4 to 2.0** -- version bump + all mechanical
   fixes from Phase 1 (1a-1f)
3. **Update tests for SQLAlchemy 2.0** -- all test file changes
   (wrap raw SQL in `text()`, replace `engine.execute()`, fix
   `MetaData(bind=...)` in tests)
4. **Use explicit transactions in `SqlTableWriter`** -- Phase 2
   changes to `writers.py` (the behavioral change), and update tests
5. **Modernization** -- Phase 4


## Risks

- **Dialect-specific upsert**: The PostgreSQL `insert().on_conflict_do_update()`
  and MySQL `insert().on_duplicate_key_update()` APIs are stable in
  SQLAlchemy 2.0. No changes needed.

- **Row access pattern**: In 1.4, `Row` supports `row['column']` and
  `dict(row)` but both emit `RemovedIn20Warning`. In 2.0, `Row` is a
  named tuple: `row[0]` and `row.column` work, but `row['column']`
  raises `TypeError` and `dict(row)` fails because `Row.keys()` is
  removed. This affects ~15 call sites in `test_writers.py`. Fix by
  calling `.mappings()` on the result, which returns `RowMapping`
  objects that support `row['column']` and `dict(row)`:
  ```python
  # Before:
  for row in connection.execute(text('SELECT ...')):
      row['id']   # TypeError in 2.0
  # After:
  for row in connection.execute(text('SELECT ...')).mappings():
      row['id']   # works
  ```
  Only test code is affected; production code doesn't iterate raw
  result rows.

- **MSSQL autocommit in tests**: `conftest.py:38,52` sets autocommit
  on the raw DBAPI connection via `conn.connection.connection.autocommit`.
  The second `.connection` accesses `ConnectionFairy.connection`, which
  is a deprecated (since 1.4.24) alias for `.dbapi_connection` and is
  removed in 2.0. Change to `conn.connection.dbapi_connection.autocommit`.
  The MSSQL CI tests will verify this.
