# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import datetime
import uuid

import pytest
import sqlalchemy

from commcare_export.checkpoint import CheckpointManager
from commcare_export.writers import SqlTableWriter

TEST_DB = 'test_commcare_export_%s' % uuid.uuid4().hex

@pytest.fixture(scope="class", params=[
    {
        'url': "postgresql://commcarehq:commcarehq@localhost/%s",
        'admin_db': 'postgres'
    },
    {
        'url': 'mysql+pymysql://root:pw@localhost/%s?charset=utf8',
    },
    {
        'url': 'sqlite:///:memory:',
        'skip_create_teardown': True,
        # http://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#using-temporary-tables-with-sqlite
        'poolclass': sqlalchemy.pool.StaticPool
    }
], ids=['postgres', 'mysql', 'sqlite'])
def db_params(request):
    try:
        sudo_engine = sqlalchemy.create_engine(request.param['url'] % request.param.get('admin_db', ''), poolclass=sqlalchemy.pool.NullPool)
    except TypeError:
        pass

    try:
        db_connection_url = request.param['url'] % TEST_DB
    except TypeError:
        db_connection_url = request.param['url']

    def tear_down():
        with sudo_engine.connect() as conn:
            conn.execute('rollback')
            conn.execute('drop database if exists %s' % TEST_DB)

    try:
        with sqlalchemy.create_engine(db_connection_url).connect():
            pass
    except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InternalError):
        with sudo_engine.connect() as conn:
            conn.execute('rollback')
            conn.execute('create database %s' % TEST_DB)
    else:
        if not request.param.get('skip_create_teardown', False):
            raise Exception('Database %s already exists; refusing to overwrite' % TEST_DB)

    if not request.param.get('skip_create_teardown', False):
        request.addfinalizer(tear_down)

    params = request.param.copy()
    params['url'] = db_connection_url
    return params



@pytest.fixture()
def writer(db_params):
    poolclass = db_params.get('poolclass', sqlalchemy.pool.NullPool)
    return SqlTableWriter(db_params['url'], poolclass=poolclass)


@pytest.fixture()
def manager(db_params):
    if 'sqlite' in db_params['url']:
        yield
    else:
        poolclass = db_params.get('poolclass', sqlalchemy.pool.NullPool)
        manager = CheckpointManager(db_params['url'], poolclass=poolclass)
        try:
            yield manager
        finally:
            with manager:
                manager.connection.execute(manager.sqlalchemy.sql.text('DROP TABLE IF EXISTS commcare_export_runs'))
                manager.connection.execute(manager.sqlalchemy.sql.text('DROP TABLE IF EXISTS alembic_version'))


MYSQL_TYPE_MAP = {
    bool: lambda x: int(x)
}


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


class TestCheckpointManager(object):
    def test_create_checkpoint_table(self, manager):
        if not manager:
            # skip sqlite
            return

        manager.create_checkpoint_table()
        with manager:
            assert 'commcare_export_runs' in manager.metadata.tables

    def test_get_time_of_last_run(self, manager):
        if not manager:
            # skip sqlite
            return

        manager.create_checkpoint_table()
        with manager:
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=True)
            second_run = datetime.datetime.utcnow()
            manager.set_checkpoint('query', '123', second_run, run_complete=True)

            assert manager.get_time_of_last_run('123') == second_run.isoformat()

    def test_clean_on_final_run(self, manager):
        if not manager:
            # skip sqlite
            return

        manager.create_checkpoint_table()
        with manager:
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
