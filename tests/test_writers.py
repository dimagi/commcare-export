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

    #def test_SqlWriter(self):
    #    writer = SqlWriter('sqlite:///:memory:')
    #    writer.write_table({
    #        'name': 'foo',
    #        'headings': ['a', 'b', 'c']
    #    })
