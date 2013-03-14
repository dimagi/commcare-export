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

    def test_SqlWriter(self):
        db = sqlalchemy.create_engine('sqlite:///:memory:')
        writer = SqlTableWriter(db)
        writer.write_table({
            'name': 'foo',
            'headings': ['a', 'b', 'c'],
            'rows': [
                [1, 2, 3],
                [4, 5, 6],
            ]
        })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        result = list(db.execute('SELECT a, b, c FROM foo'))

        assert len(result) == 2
        assert dict(result[0]) == {'a': 1, 'b': 2, 'c': 3}
        assert dict(result[1]) == {'a': 4, 'b': 5, 'c': 6}
        
