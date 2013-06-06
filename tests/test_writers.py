# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import unittest
import tempfile
import time
import uuid
import pprint
import os.path

import sqlalchemy

from commcare_export.writers import *

class TestWriters(unittest.TestCase):

    SUPERUSER_POSTGRES_URL = 'postgresql://postgres@/postgres'
    
    @classmethod
    def setup_class(cls):
        # Ensure that these URLs are good to go
        cls.TEST_SQLITE_URL = 'sqlite:///:memory:'
        cls.TEST_POSTGRES_DB = 'test_commcare_export_%s' % uuid.uuid4().hex
        cls.TEST_POSTGRES_URL = 'postgresql://postgres@/%s' % cls.TEST_POSTGRES_DB

        # For SQLite, this should work or the URL is bogus
        sqlalchemy.create_engine(cls.TEST_SQLITE_URL).connect()

        # For PostgreSQL, there are some wacky steps, and the DB name is fresh
        # via http://stackoverflow.com/questions/6506578/how-to-create-a-new-database-using-sqlalchemy
        try:
            sqlalchemy.create_engine(cls.TEST_POSTGRES_URL).connect()
        except sqlalchemy.exc.OperationalError:
            conn = sqlalchemy.create_engine(cls.SUPERUSER_POSTGRES_URL).connect()
            conn.execute('commit')
            conn.execute('create database %s' % cls.TEST_POSTGRES_DB)
            conn.close()
        else:
            raise Exception('Database %s already exists; refusing to overwrite' % cls.TEST_POSTGRES_DB)

    @classmethod
    def teardown_class(cls):
        conn = sqlalchemy.create_engine(cls.SUPERUSER_POSTGRES_URL).connect()
        conn.execute('commit')
        conn.execute('drop database %s' % cls.TEST_POSTGRES_DB)
        conn.close()

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
            assert [[cell.value for cell in row] for row in foo_sheet.range('A1:C3')] == [
                ['a', 'bjørn', 'c']
                ['1', '2', '3'],
                ['4', '日本', '6'],
            ]

    def SqlWriter_insert_tests(self, engine):
        writer = SqlTableWriter(engine) 
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
                    ['bizzle', 1, 'yo', 3],
                    ['bazzle', 4, '日本', 6],
                ]
            })
            
        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in connection.execute('SELECT id, a, b, c FROM foo_upsert')])
            
        assert len(result) == 2
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
            
        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 7, 'b': '本', 'c': 9}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': 6}

    def test_SqlWriter_insert(self):
        for url in [self.TEST_SQLITE_URL, self.TEST_POSTGRES_URL]:
            connection = sqlalchemy.create_engine(url, poolclass=sqlalchemy.pool.NullPool).connect()
            self.SqlWriter_insert_tests(connection)

    def test_SqlWriter_upsert(self):
        for url in [self.TEST_SQLITE_URL, self.TEST_POSTGRES_URL]:
            connection = sqlalchemy.create_engine(url, poolclass=sqlalchemy.pool.NullPool).connect()
            self.SqlWriter_upsert_tests(connection)
            connection.close()
