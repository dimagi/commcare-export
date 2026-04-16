# SQLAlchemy 2.0 Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade SQLAlchemy from 1.4 to 2.0 and replace the raw SQL
COMMIT hack with explicit transaction management to fix Postgres
instability with large row counts.

**Architecture:** Four commits: (1) remove unused sqlalchemy-migrate
dep, (2) bump to 2.0 + fix all deprecated API calls in production
code, (3) fix all deprecated API calls in test code, (4) replace raw
COMMIT with explicit transactions using begin/commit/rollback and
savepoints.

**Tech Stack:** SQLAlchemy 2.0, Alembic 1.18, pytest

**Spec:** `claude/specs/sqlalchemy-2.0-upgrade.md`

---

## File Map

**Production code:**
- Modify: `pyproject.toml` -- version bump, remove sqlalchemy-migrate
- Modify: `commcare_export/writers.py` -- metadata property, transaction management
- Modify: `commcare_export/checkpoint.py` -- declarative_base import
- Modify: `commcare_export/migrations/env.py` -- connection handling
- Modify: `commcare_export/migrations/versions/c36489c5a628_create_commcare_export_runs.py`
- Modify: `commcare_export/migrations/versions/d3ce9dc9907a_add_final_column.py`
- Modify: `commcare_export/migrations/versions/29c27e7e2bf6_rename_time_of_run_to_since_param.py`
- Modify: `commcare_export/migrations/versions/9945abb4ec70_add_back_time_of_run.py`

**Test code:**
- Modify: `tests/conftest.py` -- text() wrapping, dbapi_connection
- Modify: `tests/utils.py` -- engine.execute() removal
- Modify: `tests/test_writers.py` -- text() wrapping, .mappings()
- Modify: `tests/test_cli.py` -- engine.execute() removal, text(), MetaData(bind=)
- Modify: `tests/test_checkpointmanager.py` -- (no changes needed; already uses text())

---

### Task 1: Remove `sqlalchemy-migrate` dependency

**Files:**
- Modify: `pyproject.toml:47`

- [ ] **Step 1: Remove the dependency**

In `pyproject.toml`, remove the `"sqlalchemy-migrate"` line from
`dependencies`:

```python
# Before (lines 45-48):
    "sqlalchemy~=1.4",
    "sqlalchemy-migrate",
]

# After:
    "sqlalchemy~=1.4",
]
```

- [ ] **Step 2: Run tests to verify nothing breaks**

Run: `uv run pytest -m "not dbtest" -x -q`

Expected: all tests pass (nothing imports sqlalchemy-migrate)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "Remove unused sqlalchemy-migrate dependency"
```

---

### Task 2: Upgrade SQLAlchemy and fix production code

**Files:**
- Modify: `pyproject.toml:46`
- Modify: `commcare_export/writers.py:327-338`
- Modify: `commcare_export/checkpoint.py:10-18`
- Modify: `commcare_export/migrations/env.py:1-29`
- Modify: `commcare_export/migrations/versions/c36489c5a628_create_commcare_export_runs.py:19-20`
- Modify: `commcare_export/migrations/versions/d3ce9dc9907a_add_final_column.py:18-19`
- Modify: `commcare_export/migrations/versions/29c27e7e2bf6_rename_time_of_run_to_since_param.py:18-19`
- Modify: `commcare_export/migrations/versions/9945abb4ec70_add_back_time_of_run.py:19-20`

- [ ] **Step 1: Bump the version pin**

In `pyproject.toml`, change line 46:

```python
# Before:
    "sqlalchemy~=1.4",

# After:
    "sqlalchemy~=2.0",
```

- [ ] **Step 2: Sync the virtualenv**

Run: `uv sync`

This installs SQLAlchemy 2.x. Verify:

Run: `uv run python -c "import sqlalchemy; print(sqlalchemy.__version__)"`

Expected: `2.0.x` (some 2.0+ version)

- [ ] **Step 3: Fix `writers.py` metadata property**

Replace the `metadata` property at `writers.py:327-339`. The old
version binds metadata to the connection and checks connection
validity. The new version is a simple lazy init -- `get_table` already
passes `autoload_with=self.connection`, so no binding is needed.

```python
# Before (lines 327-339):
    @property
    def metadata(self):
        if (
            self._metadata is None
            or self._metadata.bind.closed
            or self._metadata.bind.invalidated
        ):
            if self.connection.closed:
                raise Exception('Tried to bind to a closed connection')
            if self.connection.invalidated:
                raise Exception('Tried to bind to an invalidated connection')
            self._metadata = sqlalchemy.MetaData(bind=self.connection)
        return self._metadata

# After:
    @property
    def metadata(self):
        if self._metadata is None:
            self._metadata = sqlalchemy.MetaData()
        return self._metadata
```

- [ ] **Step 4: Fix `checkpoint.py` declarative_base import**

`declarative_base()` from `sqlalchemy.ext.declarative` is removed in
2.0. Replace with the class-based `DeclarativeBase`.

```python
# Before (lines 9-18):
from sqlalchemy import Boolean, Column, String, and_, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

...

Base = declarative_base()


class Checkpoint(Base):  # type: ignore[misc, valid-type]

# After:
from sqlalchemy import Boolean, Column, String, and_, func
from sqlalchemy.orm import DeclarativeBase, sessionmaker

...

class Base(DeclarativeBase):
    pass


class Checkpoint(Base):  # type: ignore[misc, valid-type]
```

- [ ] **Step 5: Fix `migrations/env.py`**

In 2.0, you cannot call `.connect()` on a `Connection` (no more
"branched" connections). When `checkpoint.py` passes a `Connection`
via `cfg.attributes['connection']`, we must use it directly.

```python
# Before (full file):
from __future__ import with_statement
from alembic import context
from sqlalchemy import create_engine

config = context.config
target_metadata = None


def run_migrations_online():
    connectable = config.attributes.get('connection', None)

    if connectable is None:
        cmd_line_url = context.get_x_argument(as_dictionary=True).get('url')
        if cmd_line_url:
            connectable = create_engine(cmd_line_url)
        else:
            raise Exception("No connection URL. Use '-x url=<url>'")

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

# After:
from alembic import context
from sqlalchemy import Connection, create_engine

config = context.config
target_metadata = None


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
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
```

- [ ] **Step 6: Fix migration file `c36489c5a628`**

```python
# Before (lines 18-20):
def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    meta.reflect()

# After:
def upgrade():
    meta = sa.MetaData()
    meta.reflect(bind=op.get_bind())
```

- [ ] **Step 7: Fix migration file `d3ce9dc9907a`**

```python
# Before (lines 17-19):
def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    table = sa.Table('commcare_export_runs', meta, autoload=True)

# After:
def upgrade():
    meta = sa.MetaData()
    table = sa.Table('commcare_export_runs', meta, autoload_with=op.get_bind())
```

- [ ] **Step 8: Fix migration file `29c27e7e2bf6`**

```python
# Before (lines 17-19):
def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    table = sa.Table('commcare_export_runs', meta, autoload=True)

# After:
def upgrade():
    meta = sa.MetaData()
    table = sa.Table('commcare_export_runs', meta, autoload_with=op.get_bind())
```

- [ ] **Step 9: Fix migration file `9945abb4ec70`**

```python
# Before (lines 18-20):
def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    table = sa.Table('commcare_export_runs', meta, autoload=True)

# After:
def upgrade():
    meta = sa.MetaData()
    table = sa.Table('commcare_export_runs', meta, autoload_with=op.get_bind())
```

- [ ] **Step 10: Run non-DB tests to check for import errors**

Run: `uv run pytest -m "not dbtest" -x -q`

Expected: all pass. (DB tests will fail until test code is updated in
Task 3.)

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml commcare_export/writers.py commcare_export/checkpoint.py \
  commcare_export/migrations/env.py \
  commcare_export/migrations/versions/c36489c5a628_create_commcare_export_runs.py \
  commcare_export/migrations/versions/d3ce9dc9907a_add_final_column.py \
  commcare_export/migrations/versions/29c27e7e2bf6_rename_time_of_run_to_since_param.py \
  commcare_export/migrations/versions/9945abb4ec70_add_back_time_of_run.py
git commit -m "Upgrade SQLAlchemy 1.4 to 2.0

Remove MetaData(bind=...), autoload=True, declarative_base() import,
and branched-connection pattern in env.py."
```

---

### Task 3: Update tests for SQLAlchemy 2.0

**Files:**
- Modify: `tests/conftest.py:6,34-39,42,48-53`
- Modify: `tests/utils.py:1-18`
- Modify: `tests/test_writers.py:9,101-145,284-292,321-326,349-354,388-393,440-445,478-480,535-540,582-587,738-744,771-775,812-819,852-859,883-890`
- Modify: `tests/test_cli.py:11,530-534,614-621,649-657,848-857,893-909`

- [ ] **Step 1: Fix `tests/conftest.py`**

Add `text` import and fix all raw SQL strings. Also fix the
`dbapi_connection` access for MSSQL and add `conn.commit()` calls
(2.0 connections are not autocommit).

```python
# Before (lines 5-6):
import sqlalchemy
from sqlalchemy.exc import DBAPIError

# After:
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
```

```python
# Before (lines 33-39):
    def tear_down():
        with sudo_engine.connect() as conn:
            if 'postgres' in db_url:
                conn.execute('rollback')
            if 'mssql' in db_url:
                conn.connection.connection.autocommit = True
            conn.execute(f'drop database if exists {db_name}')

# After:
    def tear_down():
        with sudo_engine.connect() as conn:
            if 'postgres' in db_url:
                conn.execute(text('rollback'))
            if 'mssql' in db_url:
                conn.connection.dbapi_connection.autocommit = True
            conn.execute(text(f'drop database if exists {db_name}'))
            conn.commit()
```

```python
# Before (lines 41-43):
    try:
        with sqlalchemy.create_engine(db_connection_url).connect():
            pass

# After (unchanged -- this just tests connectivity, no commit needed):
    try:
        with sqlalchemy.create_engine(db_connection_url).connect():
            pass
```

```python
# Before (lines 48-53):
        with sudo_engine.connect() as conn:
            if 'postgres' in db_url:
                conn.execute('rollback')
            if 'mssql' in db_url:
                conn.connection.connection.autocommit = True
            conn.execute(f'create database {db_name}')

# After:
        with sudo_engine.connect() as conn:
            if 'postgres' in db_url:
                conn.execute(text('rollback'))
            if 'mssql' in db_url:
                conn.connection.dbapi_connection.autocommit = True
            conn.execute(text(f'create database {db_name}'))
            conn.commit()
```

- [ ] **Step 2: Fix `tests/utils.py`**

Replace `engine.execute()` (removed in 2.0) with connection context:

```python
# Before (full file):
from commcare_export.writers import SqlTableWriter


class SqlWriterWithTearDown(SqlTableWriter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tables = set()

    def write_table(self, table_spec):
        super().write_table(table_spec)
        if table_spec.rows:
            self.tables.add(table_spec.name)

    def tear_down(self):
        for table in self.tables:
            self.engine.execute(f'DROP TABLE "{table}"')
        self.tables = set()

# After:
from sqlalchemy import text

from commcare_export.writers import SqlTableWriter


class SqlWriterWithTearDown(SqlTableWriter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tables = set()

    def write_table(self, table_spec):
        super().write_table(table_spec)
        if table_spec.rows:
            self.tables.add(table_spec.name)

    def tear_down(self):
        with self.engine.connect() as conn:
            for table in self.tables:
                conn.execute(text(f'DROP TABLE "{table}"'))
            conn.commit()
        self.tables = set()
```

- [ ] **Step 3: Fix `tests/test_writers.py` -- imports and helper functions**

Add `text` import:

```python
# Before (line 9):
import sqlalchemy

# After:
import sqlalchemy
from sqlalchemy import text
```

Fix `_test_types` helper (lines 101-134). Wrap raw SQL in `text()`
and use `.mappings()` for dict-style row access:

```python
# Before (lines 101-134):
    with writer:
        connection = writer.connection
        result = dict(
            [
                (row['id'], row)
                for row in connection.execute(
                    f'SELECT id, a, b, c, d, e FROM {table_name}'
                )
            ]
        )

        assert len(result) == 2
        ...

        for id, row in result.items():
            assert id in expected
            assert dict(row) == _type_convert(connection, expected[id])

# After:
    with writer:
        connection = writer.connection
        result = dict(
            [
                (row['id'], row)
                for row in connection.execute(
                    text(f'SELECT id, a, b, c, d, e FROM {table_name}')
                ).mappings()
            ]
        )

        assert len(result) == 2
        ...

        for id, row in result.items():
            assert id in expected
            assert dict(row) == _type_convert(connection, expected[id])
```

Fix `_get_column_lengths` helper (lines 137-145):

```python
# Before:
def _get_column_lengths(connection, table_name):
    return {
        row['COLUMN_NAME']: row
        for row in connection.execute(
            'SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH '
            'FROM INFORMATION_SCHEMA.COLUMNS '
            f"WHERE TABLE_NAME = '{table_name}';"
        )
    }

# After:
def _get_column_lengths(connection, table_name):
    return {
        row['COLUMN_NAME']: row
        for row in connection.execute(
            text(
                'SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH '
                'FROM INFORMATION_SCHEMA.COLUMNS '
                f"WHERE TABLE_NAME = '{table_name}'"
            )
        ).mappings()
    }
```

- [ ] **Step 4: Fix `tests/test_writers.py` -- all remaining `.execute()` calls**

Every `writer.connection.execute('SELECT ...')` needs `text()` wrapping
and `.mappings()`. The pattern is the same throughout. All sites:

Lines 287-292 (`test_insert`):
```python
# Before:
                    (row['id'], row)
                    for row in writer.connection.execute(
                        'SELECT id, a, b, c FROM foo_insert'
                    )

# After:
                    (row['id'], row)
                    for row in writer.connection.execute(
                        text('SELECT id, a, b, c FROM foo_insert')
                    ).mappings()
```

Apply the same `text()` + `.mappings()` transformation to:
- Lines 324-326 (`test_upsert`)
- Lines 352-354 (`test_special_chars`)
- Lines 391-393 (`test_types`)
- Lines 443-445 (`test_types_via_write_table`)
- Lines 538-540 (`test_json_type`)
- Lines 585-587 (`test_all_string_types_with_strict_mode`)

For each, the change is identical: wrap the SQL string in `text()` and
append `.mappings()` to the execute call.

Lines 740-744 (`test_bulk_upsert`):
```python
# Before:
            result = {
                row['id']: dict(row)
                for row in writer.connection.execute(
                    'SELECT id, a, b FROM foo_bulk_upsert'
                )
            }

# After:
            result = {
                row['id']: dict(row)
                for row in writer.connection.execute(
                    text('SELECT id, a, b FROM foo_bulk_upsert')
                ).mappings()
            }
```

Apply the same transformation to:
- Lines 771-775 (`test_flush_batch_retry_on_new_column`)
- Lines 812-819 (`test_batched_write`)
- Lines 852-859 (`test_batched_upsert`)
- Lines 883-890 (`test_late_schema_change_via_write_table`)

Also fix the `dict(row)` calls on lines 480 (`test_types_via_write_table`)
-- this is already inside a `.mappings()` loop from the step above, so
`dict(row)` will work as-is.

- [ ] **Step 5: Fix `tests/test_cli.py` -- imports**

Add `text` import:

```python
# After line 11 (import sqlalchemy):
from sqlalchemy import text
```

- [ ] **Step 6: Fix `tests/test_cli.py` -- `_check_data` function**

Replace `engine.execute()` with connection + `text()`. This function
only reads rows as positional tuples (`list(row)`), so `.mappings()`
is not needed.

```python
# Before (lines 530-534):
def _check_data(writer, expected, table_name, columns):
    actual = [
        list(row) for row in writer.engine
        .execute(f'SELECT {", ".join(columns)} FROM "{table_name}"')
    ]

# After:
def _check_data(writer, expected, table_name, columns):
    with writer.engine.connect() as conn:
        actual = [
            list(row) for row in conn.execute(
                text(f'SELECT {", ".join(columns)} FROM "{table_name}"')
            )
        ]
```

- [ ] **Step 7: Fix `tests/test_cli.py` -- checkpoint query calls**

Lines 614-621 (`test_write_to_sql_with_checkpoints`):

```python
# Before:
        runs = list(
            writer.engine.execute(
                'SELECT * FROM commcare_export_runs '
                'WHERE query_file_name = %s',

                'tests/009_integration.xlsx'
            )
        )

# After:
        with writer.engine.connect() as conn:
            runs = list(
                conn.execute(
                    text(
                        'SELECT * FROM commcare_export_runs '
                        'WHERE query_file_name = :filename'
                    ),
                    {'filename': 'tests/009_integration.xlsx'},
                )
            )
```

Lines 649-657 (`test_write_to_sql_with_checkpoints_multiple_tables`):

```python
# Before:
        runs = list(
            writer.engine.execute(
                'SELECT table_name, since_param '
                'FROM commcare_export_runs '
                'WHERE query_file_name = %s',

                'tests/009b_integration_multiple.xlsx'
            )
        )

# After:
        with writer.engine.connect() as conn:
            runs = list(
                conn.execute(
                    text(
                        'SELECT table_name, since_param '
                        'FROM commcare_export_runs '
                        'WHERE query_file_name = :filename'
                    ),
                    {'filename': 'tests/009b_integration_multiple.xlsx'},
                )
            )
```

Lines 848-857 (`test_write_to_sql_with_conflicting_types`):

```python
# Before:
        runs = list(
            strict_writer.engine.execute(
                sqlalchemy.text(
                    'SELECT table_name, since_param, last_doc_id '
                    'FROM commcare_export_runs '
                    'WHERE query_file_name = :file'
                ),
                file='tests/013_ConflictingTypes.xlsx'
            )
        )

# After:
        with strict_writer.engine.connect() as conn:
            runs = list(
                conn.execute(
                    text(
                        'SELECT table_name, since_param, last_doc_id '
                        'FROM commcare_export_runs '
                        'WHERE query_file_name = :filename'
                    ),
                    {'filename': 'tests/013_ConflictingTypes.xlsx'},
                )
            )
```

- [ ] **Step 8: Fix `tests/test_cli.py` -- data types test**

Lines 893-909:

```python
# Before:
        metadata = sqlalchemy.schema.MetaData(bind=writer.engine)
        table = sqlalchemy.Table(
            'forms',
            metadata,
            autoload_with=writer.engine,
        )
        cols = table.c
        assert sorted([c.name for c in cols]) == sorted([
            u'id', u'a_bool', u'an_int', u'a_date', u'a_datetime', u'a_text'
        ])

        ...

        values = [
            list(row) for row in writer.engine.execute('SELECT * FROM forms')
        ]

# After:
        metadata = sqlalchemy.schema.MetaData()
        table = sqlalchemy.Table(
            'forms',
            metadata,
            autoload_with=writer.engine,
        )
        cols = table.c
        assert sorted([c.name for c in cols]) == sorted([
            u'id', u'a_bool', u'an_int', u'a_date', u'a_datetime', u'a_text'
        ])

        ...

        with writer.engine.connect() as conn:
            values = [
                list(row) for row in conn.execute(text('SELECT * FROM forms'))
            ]
```

- [ ] **Step 9: Format changed files**

Run: `uv run ruff format tests/conftest.py tests/utils.py tests/test_writers.py tests/test_cli.py`

Run: `uv run ruff check --select I --fix tests/conftest.py tests/utils.py tests/test_writers.py tests/test_cli.py`

- [ ] **Step 10: Run non-DB tests**

Run: `uv run pytest -m "not dbtest" -x -q`

Expected: all pass

- [ ] **Step 11: Run DB tests (Postgres)**

Run: `uv run pytest -m "postgres" -x -q`

Expected: all pass. If failures, debug -- the most likely cause is a
missing `text()` wrapper or missing `.mappings()`.

- [ ] **Step 12: Commit**

```bash
git add tests/conftest.py tests/utils.py tests/test_writers.py tests/test_cli.py
git commit -m "Update tests for SQLAlchemy 2.0

Wrap raw SQL in text(), replace engine.execute() with connection
context managers, use .mappings() for dict-style row access, and
fix deprecated dbapi_connection access."
```

---

### Task 4: Use explicit transactions in SqlTableWriter

This is the key behavioral change that fixes Postgres instability.

**Files:**
- Modify: `commcare_export/writers.py:289-294,587-613,658-674,676-728`
- Modify: `tests/test_writers.py:736` (the `_commit()` call in `test_bulk_upsert`)

- [ ] **Step 1: Change `__enter__`/`__exit__` to manage transactions**

```python
# Before (lines 289-294):
    def __enter__(self):
        self.connection = self.engine.connect()
        return self  # TODO: fork the writer so this can be called many times

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()

# After:
    def __enter__(self):
        self.connection = self.engine.connect()
        self.transaction = self.connection.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self.transaction.commit()
            else:
                self.transaction.rollback()
        finally:
            self.connection.close()
```

- [ ] **Step 2: Replace `_commit()` with `_flush()`**

```python
# Before (lines 610-613):
    def _commit(self):
        # Explicit commit works for all DB types. Replace with explicit
        # transactions when upgrading to SQLAlchemy 2.0
        self.connection.execute(sqlalchemy.text('COMMIT'))

# After:
    def _flush(self):
        self.transaction.commit()
        self.transaction = self.connection.begin()
```

- [ ] **Step 3: Update `upsert()` to use savepoints**

On Postgres, an `IntegrityError` inside a transaction puts the
transaction in an error state. Savepoints isolate the failed INSERT
so the UPDATE can proceed within the same transaction.

```python
# Before (lines 587-608):
    def upsert(self, table, row_dict):
        # For atomicity "insert, catch, update" is slightly better than
        # "select, insert or update". The latter may crash, while the
        # former may overwrite data (which should be fine if whatever is
        # racing against this is importing from the same source... if
        # not you are busted anyhow

        # strip out values that are None since the column may not exist
        # yet
        row_dict = {
            col: val for col, val in row_dict.items() if val is not None
        }
        try:
            insert = table.insert().values(**row_dict)
            self.connection.execute(insert)
        except sqlalchemy.exc.IntegrityError:
            update = (
                table.update()
                .where(table.c.id == row_dict['id'])
                .values(**row_dict)
            )
            self.connection.execute(update)

# After:
    def upsert(self, table, row_dict):
        # For atomicity "insert, catch, update" is slightly better than
        # "select, insert or update". The latter may crash, while the
        # former may overwrite data (which should be fine if whatever is
        # racing against this is importing from the same source... if
        # not you are busted anyhow

        # strip out values that are None since the column may not exist
        # yet
        row_dict = {
            col: val for col, val in row_dict.items() if val is not None
        }
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

- [ ] **Step 4: Update `_flush_batch()` to handle transaction state on error**

After a failed `bulk_upsert`, the transaction is in an error state
(especially on Postgres). Roll back and start a new transaction before
retrying.

```python
# Before (lines 658-674):
    def _flush_batch(self, table, batch, data_type_dict):
        try:
            self.bulk_upsert(table, batch)
        except (
            sqlalchemy.exc.CompileError,
            sqlalchemy.exc.OperationalError,
            sqlalchemy.exc.ProgrammingError,
        ):
            # Likely a schema mismatch; fix schema and retry once
            for row_dict in batch:
                table = self.make_table_compatible(
                    table,
                    row_dict,
                    data_type_dict,
                )
            self.bulk_upsert(table, batch)
        self._commit()

# After:
    def _flush_batch(self, table, batch, data_type_dict):
        try:
            self.bulk_upsert(table, batch)
        except (
            sqlalchemy.exc.CompileError,
            sqlalchemy.exc.OperationalError,
            sqlalchemy.exc.ProgrammingError,
        ):
            # Likely a schema mismatch; roll back failed transaction,
            # fix schema, and retry once
            self.transaction.rollback()
            self.transaction = self.connection.begin()
            for row_dict in batch:
                table = self.make_table_compatible(
                    table,
                    row_dict,
                    data_type_dict,
                )
            self.bulk_upsert(table, batch)
        self._flush()
```

- [ ] **Step 5: Update `write_table()` -- replace `_commit` with `_flush`**

Replace all `self._commit()` calls with `self._flush()`:

```python
# Line 710 (after schema check phase):
# Before:
                    self._commit()
# After:
                    self._flush()

# Line 728 (schema-check-only path):
# Before:
            self._commit()
# After:
            self._flush()
```

Note: the `_flush_batch` call on line 674 already has `self._flush()`
from Step 4. The `__exit__` method commits the final transaction.

- [ ] **Step 6: Update test that calls `_commit()` directly**

`test_writers.py:736` calls `writer._commit()` directly in
`test_bulk_upsert`:

```python
# Before (line 736):
            writer._commit()

# After:
            writer._flush()
```

- [ ] **Step 7: Format changed files**

Run: `uv run ruff format commcare_export/writers.py tests/test_writers.py`

Run: `uv run ruff check --select I --fix commcare_export/writers.py tests/test_writers.py`

- [ ] **Step 8: Run type checker**

Run: `uv run mypy commcare_export/ tests/`

Expected: no new errors

- [ ] **Step 9: Run non-DB tests**

Run: `uv run pytest -m "not dbtest" -x -q`

Expected: all pass

- [ ] **Step 10: Run DB tests (Postgres)**

Run: `uv run pytest -m "postgres" -x -q`

Expected: all pass. This is the critical verification -- the explicit
transaction management must work correctly on Postgres.

- [ ] **Step 11: Commit**

```bash
git add commcare_export/writers.py tests/test_writers.py
git commit -m "Use explicit transactions in SqlTableWriter

Replace raw SQL COMMIT with SQLAlchemy 2.0 transaction API:
- __enter__/__exit__ manage begin/commit/rollback
- _flush() commits current transaction and starts a new one
- upsert() uses savepoints for insert-or-update on Postgres
- _flush_batch() rolls back failed transaction before retry"
```
