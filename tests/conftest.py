# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import uuid

import pytest
import sqlalchemy

TEST_DB = 'test_commcare_export_%s' % uuid.uuid4().hex

@pytest.fixture(scope="class", params=[
    {
        'url': "postgresql://postgres@/%s",
        'admin_db': 'postgres'
    },
    {
        'url': 'mysql+pymysql://travis@/%s?charset=utf8',
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
