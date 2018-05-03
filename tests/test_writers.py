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
    poolclass = db_params.get('poolclass', sqlalchemy.pool.NullPool)
    return SqlTableWriter(db_params['url'], poolclass=poolclass)


MYSQL_TYPE_MAP = {
    bool: lambda x: int(x)
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


class TestSQLWriters(object):
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

    def test_insert(self, writer):
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
        with writer:
            result = dict([(row['id'], row) for row in writer.connection.execute('SELECT id, a, b, c FROM foo_insert')])

        assert len(result) == 2
        assert dict(result['bizzle']) == {'id': 'bizzle', 'a': 1, 'b': 2, 'c': 3}
        assert dict(result['bazzle']) == {'id': 'bazzle', 'a': 4, 'b': 5, 'c': 6}

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
            if writer.is_sqllite:
                # These tests cannot be accomplished with Sqlite
                # because it does not support these
                # core features such as column type changes
                return

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
            assert dict(result['bizzle']) == self._type_convert(connection,
                                                                {'id': 'bizzle', 'a': 1, 'b': 'yo', 'c': True,
                                                                 'd': datetime.date(2015, 1, 1),
                                                                 'e': datetime.datetime(2014, 4, 2, 18, 56, 12)})
            assert dict(result['bazzle']) == self._type_convert(connection,
                                                                {'id': 'bazzle', 'a': 4, 'b': '日本', 'c': False,
                                                                 'd': datetime.date(2015, 1, 2),
                                                                 'e': datetime.datetime(2014, 5, 1, 11, 16, 45)})

    def test_change_type(self, writer):
        self._test_types(writer, 'foo_fancy_type_changes')

        with writer:
            if writer.is_sqllite:
                # These tests cannot be accomplished with Sqlite
                # because it does not support these
                # core features such as column type changes
                return

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

        for id, row in result.items():
            assert id in expected
            assert dict(row) == expected[id]
