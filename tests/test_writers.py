# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import datetime
import tempfile

import openpyxl
import pytest
import sqlalchemy

from commcare_export.writers import SqlTableWriter, JValueTableWriter, Excel2007TableWriter


@pytest.fixture()
def writer(db_params):
    return SqlTableWriter(db_params['url'], poolclass=sqlalchemy.pool.NullPool)


TYPE_MAP = {
    'mysql': {
        bool: lambda x: int(x)
    },
}


class TestWriters(object):
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

        writer.write_table({
            'name': 'foo',
            'headings': ['a', 'bjørn', 'c', 'd'],
            'rows': [
                [5, 'bob', 9, datetime.date(2018, 1, 2)],
            ]
        })

        assert writer.tables == {
            'foo': {
                'name': 'foo',
                'headings': ['a', 'bjørn', 'c', 'd'],
                'rows': [
                    [1, '2', 3, '2015-01-01'],
                    [4, '日本', 6, '2015-01-02'],
                    [5, 'bob', 9, '2018-01-02'],
                ],
            }
        }

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

            self._check_Excel2007TableWriter_output(file.name)

    def test_Excel2007TableWriter_write_mutli(self):
        with tempfile.NamedTemporaryFile() as file:
            with Excel2007TableWriter(file=file) as writer:
                writer.write_table({
                    'name': 'foo',
                    'headings': ['a', 'bjørn', 'c'],
                    'rows': [
                        [1, '2', 3],
                    ]
                })

                writer.write_table({
                    'name': 'foo',
                    'headings': ['a', 'bjørn', 'c'],
                    'rows': [
                        [4, '日本', 6],
                    ]
                })
            self._check_Excel2007TableWriter_output(file.name)

    def _check_Excel2007TableWriter_output(self, filename):
            output_wb = openpyxl.load_workbook(filename)

            assert list(output_wb.get_sheet_names()) == ['foo']
            foo_sheet = output_wb.get_sheet_by_name('foo')
            assert [ [cell.value for cell in row] for row in foo_sheet.range('A1:C3')] == [
                ['a', 'bjørn', 'c'],
                ['1', '2', '3'], # Note how pyxl does some best-effort parsing to *whatever* type
                ['4', '日本', '6'],
            ]


@pytest.mark.dbtest
class TestSQLWriters(object):
    def _type_convert(self, connection, row):
        """
        Different databases store and return values differently so convert the values
        in the expected row to match the DB.
        """
        def convert(type_map, value):
            func = type_map.get(value.__class__, None)
            return func(value) if func else value

        for driver, type_map in TYPE_MAP.items():
            if driver in connection.engine.driver:
                return {k: convert(type_map, v) for k, v in row.items()}

        return row

    def test_insert(self, writer):
        with writer:
            writer.write_table({
                'name': 'foo_insert',
                'headings': ['id', 'a', 'b', 'c', 's'],
                'rows': [
                    ['bizzle', 1, 2, 3, 'hi'],
                    ['bazzle', 4, 5, 6, 'hello'],
                    ['bozzle', 7, 8, 9, {'#text': 'test_text','@case_type': 'person','@relationship': 'child','id': 'nothing'}],
                    ['buzzle', 1, 8, 7, {'@case_type': '', '@relationship': 'child', 'id': 'some_id'}],
                ]
            })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        with writer:
            result = dict([(row['id'], row) for row in writer.connection.execute('SELECT id, a, b, c, s FROM foo_insert')])

        assert len(result) == 4
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 1, 'b': 2, 'c': 3, 's': 'hi'}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': 5, 'c': 6, 's': 'hello'}
        assert dict(result['bozzle']) == {'id': 'bazzle', 'a': 7, 'b': 8, 'c': 9, 's': 'test_text'}
        assert dict(result['buzzle']) == {'id': 'bazzle', 'a': 1, 'b': 8, 'c': 7, 's': ''}

    def test_upsert(self, writer):
        with writer:
            writer.write_table({
                'name': 'foo_upsert',
                'headings': ['id', 'a', 'b', 'c'],
                'rows': [
                    ['zing', 3, None, 5]
                ]
            })

        # don't select column 'b' since it hasn't been created yet
        with writer:
            result = dict([(row['id'], row) for row in writer.connection.execute('SELECT id, a, c FROM foo_upsert')])
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
        with writer:
            result = dict([(row['id'], row) for row in writer.connection.execute('SELECT id, a, b, c FROM foo_upsert')])

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
        with writer:
            result = dict([(row['id'], row) for row in writer.connection.execute('SELECT id, a, b, c FROM foo_upsert')])

        assert len(result) == 3
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 7, 'b': '本', 'c': 9}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': 6}

    def test_types(self, writer):
        self._test_types(writer, 'foo_fancy_types')

    def _test_types(self, writer, table_name):
        with writer:
            writer.write_table({
                'name': table_name,
                'headings': ['id', 'a', 'b', 'c', 'd', 'e'],
                'rows': [
                    ['bizzle', 1, 'yo', True, datetime.date(2015, 1, 1), datetime.datetime(2014, 4, 2, 18, 56, 12)],
                    ['bazzle', 4, '日本', False, datetime.date(2015, 1, 2), datetime.datetime(2014, 5, 1, 11, 16, 45)],
                ]
            })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        with writer:
            connection = writer.connection
            result = dict(
                [(row['id'], row) for row in connection.execute('SELECT id, a, b, c, d, e FROM %s' % table_name)])

            assert len(result) == 2
            expected = {
                'bizzle': {'id': 'bizzle', 'a': 1, 'b': 'yo', 'c': True,
                           'd': datetime.date(2015, 1, 1), 'e': datetime.datetime(2014, 4, 2, 18, 56, 12)},
                'bazzle': {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': False,
                           'd': datetime.date(2015, 1, 2), 'e': datetime.datetime(2014, 5, 1, 11, 16, 45)}
            }

            for id, row in result.items():
                assert id in expected
                assert dict(row) == self._type_convert(connection, expected[id])

    def test_change_type(self, writer):
        self._test_types(writer, 'foo_fancy_type_changes')

        with writer:
            writer.write_table({
                'name': 'foo_fancy_type_changes',
                'headings': ['id', 'a', 'b', 'c', 'd', 'e'],
                'rows': [
                    ['bizzle', 'yo dude', '本', 'true', datetime.datetime(2015, 2, 13), '2014-08-01T11:23:45:00.0000Z'],
                ]
            })

        # We can use raw SQL instead of SqlAlchemy expressions because we built the DB above
        with writer:
            result = dict([(row['id'], row) for row in
                           writer.connection.execute('SELECT id, a, b, c, d, e FROM foo_fancy_type_changes')])

        assert len(result) == 2
        expected = {
            'bizzle': {'id': 'bizzle', 'a': 'yo dude', 'b': '本', 'c': 'true',
                       'd': datetime.date(2015, 2, 13), 'e': '2014-08-01T11:23:45:00.0000Z'},
            'bazzle': {'id': 'bazzle', 'a': '4', 'b': '日本', 'c': 'false',
                       'd': datetime.date(2015, 1, 2), 'e': '2014-05-01 11:16:45'}
        }

        if 'mysql' in writer.connection.engine.driver:
            # mysql weirdness
            expected['bazzle']['c'] = '0'
        if 'pyodbc' in writer.connection.engine.driver:
            expected['bazzle']['c'] = '0'
            # couldn't figure out how to make SQL Server convert date to ISO8601
            # see https://docs.microsoft.com/en-us/sql/t-sql/functions/cast-and-convert-transact-sql?view=sql-server-2017#date-and-time-styles
            expected['bazzle']['e'] = 'May  1 2014 11:16AM'

        for id, row in result.items():
            assert id in expected
            assert dict(row) == expected[id]
