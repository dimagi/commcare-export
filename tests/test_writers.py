# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import unittest
import tempfile
import uuid

import openpyxl
import sqlalchemy

from commcare_export.writers import *

class TestWriters(unittest.TestCase):

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

    def test_JValueTableWriter(self):
        writer = JValueTableWriter()
        writer.write_table({
            'name': 'foo',
            'headings': ['a', 'bjørn', 'c'],
            'rows': [
                [1, '2', 3],
                [4, '日本', 6],
            ]
        })

        assert writer.tables == [{
            'name': 'foo',
            'headings': ['a', 'bjørn', 'c'],
            'rows': [
                [1, '2', 3],
                [4, '日本', 6],
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
                [1, 2, 3], # Note how pyxl does some best-effort parsing to *whatever* type
                [4, '日本', 6],
            ]

    def SqlWriter_insert_tests(self, engine):
        writer = SqlTableWriter(engine.connect())
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

    def SqlWriter_upsert_tests(self, connection):
        writer = SqlTableWriter(connection)

        with writer:
            writer.write_table({
                'name': 'foo_upsert',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['zing', 3, None, 5] # The None is allowed only in string fields as it defaults the col to text
                ]
            })

        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c FROM foo_upsert')])
        assert len(result) == 1
        assert dict(result['zing']) == {'id': 'zing', 'a': 3, 'b': None, 'c': 5}

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

    def SqlWriter_fancy_tests(self, connection):
        writer = SqlTableWriter(connection)
        with writer:
            writer.write_table({
                'name': 'foo_fancy',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['bizzle', 1, 'yo', 3],
                    ['bazzle', 4, '日本', 6],
                ]
            })
            
        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c FROM foo_fancy')])
            
        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 1, 'b': 'yo', 'c': 3}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': 6}

        writer = SqlTableWriter(connection)
        with writer:
            writer.write_table({
                'name': 'foo_fancy',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['bizzle', 'yo dude', '本', 9],
                ]
            })
            
        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c FROM foo_fancy')])
            
        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 'yo dude', 'b': '本', 'c': 9}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': '4', 'b': '日本', 'c': 6}

    def test_postgres_insert(self):
        with self.postgres_engine.connect() as conn:
            self.SqlWriter_insert_tests(conn)

    def test_mysql_insert(self):
        with self.mysql_engine.connect() as conn:
            self.SqlWriter_insert_tests(conn)

    def test_sqlite_insert(self):
        # SQLite requires a connection, not just an engine, or the created tables seem to never commit.
        with self.sqlite_engine.connect() as conn:
            self.SqlWriter_insert_tests(conn)

    def test_postgres_upsert(self):
        with self.postgres_engine.connect() as conn:
            self.SqlWriter_upsert_tests(conn)

    def test_mysql_upsert(self):
        with self.mysql_engine.connect() as conn:
            self.SqlWriter_upsert_tests(conn)

    def test_sqlite_upsert(self):
        with self.sqlite_engine.connect() as conn:
            self.SqlWriter_upsert_tests(conn)

    def test_postgres_fancy(self):
        '''
        These tests cannot be accomplished with Sqlite because it does not support these
        core features such as column type changes
        '''
        with self.postgres_engine.connect() as conn:
            self.SqlWriter_fancy_tests(conn)

    def test_mysql_fancy(self):
        '''
        These tests cannot be accomplished with Sqlite because it does not support these
        core features such as column type changes
        '''
        with self.mysql_engine.connect() as conn:
            self.SqlWriter_fancy_tests(conn)
