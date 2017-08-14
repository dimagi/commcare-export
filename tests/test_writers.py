# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import inspect
import unittest
import tempfile
import uuid

import openpyxl
import sqlalchemy

from commcare_export.checkpoint import CheckpointManager
from commcare_export.writers import *

MYSQL_TYPE_MAP = {
    bool: lambda x: int(x)
}

class SqlTestMixin(object):

    SUPERUSER_POSTGRES_URL = 'postgresql://postgres@/postgres'
    SUPERUSER_MYSQL_URL = 'mysql+pymysql://travis@/?charset=utf8'

    @classmethod
    def setup_class(cls):
        # Ensure that these URLs are good to go
        cls.TEST_SQLITE_URL = 'sqlite:///:memory:'
        cls.TEST_POSTGRES_DB = 'test_commcare_export_%s' % uuid.uuid4().hex
        cls.TEST_POSTGRES_URL = 'postgresql://postgres@/%s' % cls.TEST_POSTGRES_DB
        cls.TEST_MYSQL_DB = 'test_commcare_export_%s' % uuid.uuid4().hex
        cls.TEST_MYSQL_URL = 'mysql+pymysql://travis@/%s?charset=utf8' % cls.TEST_MYSQL_DB

        # "Engines" are not actual connections, but vend connections
        cls.postgres_sudo_engine = sqlalchemy.create_engine(cls.SUPERUSER_POSTGRES_URL, poolclass=sqlalchemy.pool.NullPool)
        cls.postgres_engine = sqlalchemy.create_engine(cls.TEST_POSTGRES_URL, poolclass=sqlalchemy.pool.NullPool)
        cls.mysql_sudo_engine = sqlalchemy.create_engine(cls.SUPERUSER_MYSQL_URL, poolclass=sqlalchemy.pool.NullPool)
        cls.mysql_engine = sqlalchemy.create_engine(cls.TEST_MYSQL_URL, poolclass=sqlalchemy.pool.NullPool)
        cls.sqlite_engine = sqlalchemy.create_engine(cls.TEST_SQLITE_URL, poolclass=sqlalchemy.pool.NullPool)

        # For SQLite, this should work or the URL is bogus
        with cls.sqlite_engine.connect() as conn:
            pass

        # SQLAlchemy starts connections in a transaction, so we need to rollback immediately
        # before doing database creation and dropping
        # via http://stackoverflow.com/questions/6506578/how-to-create-a-new-database-using-sqlalchemy

        # PostgreSQL
        try:
            with cls.postgres_engine.connect():
                pass
        except sqlalchemy.exc.OperationalError:
            with cls.postgres_sudo_engine.connect() as conn:
                conn.execute('rollback')
                conn.execute('create database %s' % cls.TEST_POSTGRES_DB)
        else:
            raise Exception('Database %s already exists; refusing to overwrite' % cls.TEST_POSTGRES_DB)

        # MySQL
        try:
            with cls.mysql_engine.connect():
                pass
        except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InternalError) as e:
            with cls.mysql_sudo_engine.connect() as conn:
                conn.execute('rollback')
                conn.execute('create database %s' % cls.TEST_MYSQL_DB)
        else:
            raise Exception('Database %s already exists; refusing to overwrite' % cls.TEST_MYSQL_DB)

    @classmethod
    def teardown_class(cls):
        with cls.postgres_sudo_engine.connect() as conn:
            conn.execute('rollback')
            conn.execute('drop database if exists %s' % cls.TEST_POSTGRES_DB)

        with cls.mysql_sudo_engine.connect() as conn:
            conn.execute('rollback')
            conn.execute('drop database if exists %s' % cls.TEST_MYSQL_DB)

class TestWriters(SqlTestMixin, unittest.TestCase):

    def _type_convert(self, connection, row):
        """
        Different databases store and return values differently so convert the values
        in the expected row to match the DB.
        """
        def convert(type_map, value):
            func = type_map.get(value.__class__, None)
            return func(value) if func else value

        if 'mysql' in connection.engine.driver:
            return {k: convert(MYSQL_TYPE_MAP, v) for k, v in row.items()}

        return row

    def test_JValueTableWriter(self):
        writer = JValueTableWriter()
        writer.write_table({
            'name': 'foo',
            'headings': ['a', 'bjørn', 'c', 'd'],
            'rows': [
                [1, '2', 3, datetime.date(2015, 1, 1)],
                [4, '日本', 6, datetime.date(2015, 1, 2)],
            ]
        })

        assert writer.tables == [{
            'name': 'foo',
            'headings': ['a', 'bjørn', 'c', 'd'],
            'rows': [
                [1, '2', 3, '2015-01-01'],
                [4, '日本', 6, '2015-01-02'],
            ],
        }]

    def test_Excel2007TableWriter(self):
        with tempfile.NamedTemporaryFile() as file:
            with Excel2007TableWriter(file=file) as writer:
                writer.write_table({
                    'name': 'foo',
                    'headings': ['a', 'bjørn', 'c'],
                    'rows': [
                        [1, '2', 3],
                        [4, '日本', 6],
                    ]
                })

            output_wb = openpyxl.load_workbook(file.name)

            assert list(output_wb.get_sheet_names()) == ['foo']
            foo_sheet = output_wb.get_sheet_by_name('foo')
            assert [ [cell.value for cell in row] for row in foo_sheet.range('A1:C3')] == [
                ['a', 'bjørn', 'c'],
                ['1', '2', '3'], # Note how pyxl does some best-effort parsing to *whatever* type
                ['4', '日本', '6'],
            ]

    def SqlWriter_insert_tests(self, engine, is_mysql=False):
        writer = self.get_sql_writer(engine.connect(), is_mysql)
        with writer:
            writer.write_table({
                'name': 'foo_insert',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['bizzle', 1, 2, 3],
                    ['bazzle', 4, 5, 6],
                ]
            })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in engine.execute('SELECT id, a, b, c FROM foo_insert')])

        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 1, 'b': 2, 'c': 3}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': 5, 'c': 6}

    def SqlWriter_upsert_tests(self, connection, is_mysql=False):
        writer = self.get_sql_writer(connection, is_mysql)

        with writer:
            writer.write_table({
                'name': 'foo_upsert',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['zing', 3, None, 5]
                ]
            })

        # don't select column 'b' since it hasn't been created yet
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, c FROM foo_upsert')])
        assert len(result) == 1
        assert dict(result['zing']) == {'id': 'zing', 'a': 3, 'c': 5}

        with writer:
            writer.write_table({
                'name': 'foo_upsert',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['bizzle', 1, 'yo', 3],
                    ['bazzle', 4, '日本', 6],
                ]
            })
            
        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c FROM foo_upsert')])
            
        assert len(result) == 3
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 1, 'b': 'yo', 'c': 3}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': 6}

        with writer:
            writer.write_table({
                'name': 'foo_upsert',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['bizzle', 7, '本', 9],
                ]
            })
            
        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c FROM foo_upsert')])
            
        assert len(result) == 3
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 7, 'b': '本', 'c': 9}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': 6}

    def SqlWriter_types_test(self, connection, table_name=None, is_mysql=False):
        table_name = table_name or 'foo_fancy_types'
        writer = self.get_sql_writer(connection, is_mysql)
        with writer:
            writer.write_table({
                'name': table_name or 'foo_fancy_types',
                'headings': ['id', 'a', 'b', 'c', 'd', 'e'],
                'rows': [
                    ['bizzle', 1, 'yo', True, datetime.date(2015, 1, 1), datetime.datetime(2014, 4, 2, 18, 56, 12)],
                    ['bazzle', 4, '日本', False, datetime.date(2015, 1, 2), datetime.datetime(2014, 5, 1, 11, 16, 45)],
                ]
            })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c, d, e FROM %s' % table_name)])

        assert len(result) == 2
        assert dict(result['bizzle']) == self._type_convert(connection, {'id': 'bizzle', 'a': 1, 'b': 'yo', 'c': True,
                                          'd': datetime.date(2015, 1, 1), 'e': datetime.datetime(2014, 4, 2, 18, 56, 12)})
        assert dict(result['bazzle']) == self._type_convert(connection, {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': False,
                                          'd': datetime.date(2015, 1, 2), 'e': datetime.datetime(2014, 5, 1, 11, 16, 45)})

    def SqlWriter_change_type_test(self, connection, expected, is_mysql=False):
        self.SqlWriter_types_test(connection, 'foo_fancy_type_changes', is_mysql=is_mysql)

        writer = self.get_sql_writer(connection, is_mysql)
        with writer:
            writer.write_table({
                'name': 'foo_fancy_type_changes',
                'headings': ['id', 'a', 'b', 'c', 'd', 'e'],
                'rows': [
                    ['bizzle', 'yo dude', '本', 'true', datetime.datetime(2015, 2, 13), '2014-08-01T11:23:45:00.0000Z'],
                ]
            })
            
        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c, d, e FROM foo_fancy_type_changes')])
            
        assert len(result) == 2
        for id, row in result.items():
            assert id in expected
            assert dict(row) == expected[id]

    def get_sql_writer(self, connection, is_mysql):
        collation = 'utf8_bin' if is_mysql else None
        writer = SqlTableWriter(connection, collation=collation)
        return writer

    def test_postgres_insert(self):
        with self.postgres_engine.connect() as conn:
            self.SqlWriter_insert_tests(conn)

    def test_mysql_insert(self):
        with self.mysql_engine.connect() as conn:
            self.SqlWriter_insert_tests(conn, is_mysql=True)

    def test_sqlite_insert(self):
        # SQLite requires a connection, not just an engine, or the created tables seem to never commit.
        with self.sqlite_engine.connect() as conn:
            self.SqlWriter_insert_tests(conn)

    def test_postgres_upsert(self):
        with self.postgres_engine.connect() as conn:
            self.SqlWriter_upsert_tests(conn)

    def test_mysql_upsert(self):
        with self.mysql_engine.connect() as conn:
            self.SqlWriter_upsert_tests(conn, is_mysql=True)

    def test_sqlite_upsert(self):
        with self.sqlite_engine.connect() as conn:
            self.SqlWriter_upsert_tests(conn)

    def test_postgres_type_changes(self):
        '''
        These tests cannot be accomplished with Sqlite because it does not support these
        core features such as column type changes
        '''
        expected = {
            'bizzle': {'id': 'bizzle', 'a': 'yo dude', 'b': '本', 'c': 'true',
                       'd': datetime.date(2015, 2, 13), 'e': '2014-08-01T11:23:45:00.0000Z'},
            'bazzle': {'id': 'bazzle', 'a': '4', 'b': '日本', 'c': 'false',
                       'd': datetime.date(2015, 1, 2), 'e': '2014-05-01 11:16:45'}
        }
        with self.postgres_engine.connect() as conn:
            self.SqlWriter_change_type_test(conn, expected)

    def test_postgres_types(self):
        '''
        These tests cannot be accomplished with Sqlite because it does not support these
        core features such as column type changes
        '''
        with self.postgres_engine.connect() as conn:
            self.SqlWriter_types_test(conn)

    def test_mysql_type_changes(self):
        '''
        These tests cannot be accomplished with Sqlite because it does not support these
        core features such as column type changes
        '''
        expected = {
            'bizzle': {'id': 'bizzle', 'a': 'yo dude', 'b': '本', 'c': 'true',
                       'd': datetime.date(2015, 2, 13), 'e': '2014-08-01T11:23:45:00.0000Z'},
            'bazzle': {'id': 'bazzle', 'a': '4', 'b': '日本', 'c': '0',
                       'd': datetime.date(2015, 1, 2), 'e': '2014-05-01 11:16:45'}
        }
        with self.mysql_engine.connect() as conn:
            self.SqlWriter_change_type_test(conn, expected, is_mysql=True)

    def test_mysql_types(self):
        '''
        These tests cannot be accomplished with Sqlite because it does not support these
        core features such as column type changes
        '''
        with self.mysql_engine.connect() as conn:
            self.SqlWriter_types_test(conn, is_mysql=True)


def make_test_cases(cls):
    """For each '_test_*' method on the class create a test case for each sql engine"""
    engines = ('mysql_engine', 'postgres_engine')
    methods = inspect.getmembers(cls, predicate=inspect.ismethod)
    for name, method in methods:
        if name.startswith('_test_'):
            def _make_test_cases(test_method, sql_engine):
                # closure to make sure test_method is the right method
                def test(self):
                    with getattr(self, sql_engine).connect() as conn:
                        manager = self.get_checkpointer(conn, 'mysql' in sql_engine)
                        test_method(self, manager)

                test.__name__ = str('{}_{}'.format(name[1:], sql_engine))
                assert not hasattr(cls, test.__name__), \
                    "duplicate test case: {} {}".format(cls, test.__name__)

                setattr(cls, test.__name__, test)

            for engine in engines:
                _make_test_cases(method, engine)
    return cls


@make_test_cases
class TestCheckpointManager(SqlTestMixin, unittest.TestCase):

    def tearDown(self):
        with self.postgres_engine.connect() as conn:
            self._tearDown(self.get_checkpointer(conn, False))
        with self.mysql_engine.connect() as conn:
            self._tearDown(self.get_checkpointer(conn, True))
        super(TestCheckpointManager, self).tearDown()

    def _tearDown(self, manager):
        with manager:
            if manager.table_name in manager.metadata.tables:
                manager.connection.execute(manager.sqlalchemy.sql.text('DROP TABLE commcare_export_runs'))

    def get_checkpointer(self, connection, is_mysql):
        collation = 'utf8_bin' if is_mysql else None
        writer = CheckpointManager(connection, collation=collation)
        return writer

    def _test_create_checkpoint_table(self, manager):
        with manager:
            manager.create_checkpoint_table()
            assert 'commcare_export_runs' in manager.metadata.tables

    def _test_update_checkpoint_table(self, manager):
        with manager:
            # create table with some columns missing
            all_columns = manager._get_checkpoint_table_columns()
            some_columns = all_columns[:-1]
            manager._migrate_checkpoint_table(some_columns)
            assert 'commcare_export_runs' in manager.metadata.tables
            assert {col.name for col in some_columns} == {c.name for c in manager.table('commcare_export_runs').columns}

            manager.create_checkpoint_table()
            assert {col.name for col in all_columns} == {c.name for c in manager.table('commcare_export_runs').columns}

    def _test_get_time_of_last_run(self, manager):
        with manager:
            manager.create_checkpoint_table()
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=True)
            second_run = datetime.datetime.utcnow()
            manager.set_checkpoint('query', '123', second_run, run_complete=True)

            assert manager.get_time_of_last_run('123') == second_run.isoformat()

    def _test_clean_on_final_run(self, manager):
        with manager:
            manager.create_checkpoint_table()
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=False)
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=False)

            def _get_non_final_rows_count():
                cursor = manager.connection.execute(
                    manager.sqlalchemy.sql.text('select count(*) from {} where final = :final'.format(manager.table_name)),
                    final=False
                )
                for row in cursor:
                    return row[0]

            assert _get_non_final_rows_count() == 2
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=True)
            assert _get_non_final_rows_count() == 0

