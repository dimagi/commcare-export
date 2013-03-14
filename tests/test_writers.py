import unittest
import pprint
import os.path

import openpyxl
import xlwt
import sqlalchemy

from commcare_export.writers import *

class TestWriters(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_JValueTableWriter(self):
        writer = JValueTableWriter()
        writer.write_table({
            'name': 'foo',
            'headings': ['a', 'b', 'c'],
            'rows': [
                [1, 2, 3],
                [4, 5, 6],
            ]
        })

        assert writer.tables == [{
            'name': 'foo',
            'headings': ['a', 'b', 'c'],
            'rows': [
                [1, 2, 3],
                [4, 5, 6],
            ],
        }]

    def test_SqlWriter_insert(self):
        db = sqlalchemy.create_engine('sqlite:///:memory:')
        writer = SqlTableWriter(db)
        writer.write_table({
            'name': 'foo',
            'headings': ['id', 'a', 'b', 'c'],
            'rows': [
                ['bizzle', 1, 2, 3],
                ['bazzle', 4, 5, 6],
            ]
        })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in db.execute('SELECT id, a, b, c FROM foo')])

        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 1, 'b': 2, 'c': 3}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': 5, 'c': 6}

    def test_SqlWriter_update(self):
        db = sqlalchemy.create_engine('sqlite:///:memory:')
        writer = SqlTableWriter(db)
        writer.write_table({
            'name': 'foo',
            'headings': ['id', 'a', 'b', 'c'],
            'rows': [
                ['bizzle', 1, 2, 3],
                ['bazzle', 4, 5, 6],
            ]
        })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in db.execute('SELECT id, a, b, c FROM foo')])

        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 1, 'b': 2, 'c': 3}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': 5, 'c': 6}

        writer.write_table({
            'name': 'foo',
            'headings': ['id', 'a', 'b', 'c'],
            'rows': [
                ['bizzle', 7, 8, 9],
            ]
        })
        
        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = dict([(row['id'], row) for row in db.execute('SELECT id, a, b, c FROM foo')])

        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 7, 'b': 8, 'c': 9}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': 5, 'c': 6}
