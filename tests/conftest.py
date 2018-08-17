# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import logging
import uuid

import pytest
import sqlalchemy
from sqlalchemy.exc import DBAPIError

TEST_DB = 'test_commcare_export_%s' % uuid.uuid4().hex

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler())


def _db_params(request, db_name):
    db_url = request.param['url']
    sudo_engine = sqlalchemy.create_engine(db_url % request.param.get('admin_db', ''), poolclass=sqlalchemy.pool.NullPool)
    db_connection_url = db_url % db_name

    def tear_down():
        with sudo_engine.connect() as conn:
            conn.execute('rollback')
            if 'mssql' in db_url:
                conn.connection.connection.autocommit = True
            conn.execute('drop database if exists %s' % db_name)

    try:
        with sqlalchemy.create_engine(db_connection_url).connect():
            pass
    except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InternalError, DBAPIError):
        with sudo_engine.connect() as conn:
            conn.execute('rollback')
            if 'mssql' in db_url:
                conn.connection.connection.autocommit = True
            conn.execute('create database %s' % db_name)
    else:
        raise Exception('Database %s already exists; refusing to overwrite' % db_name)

    request.addfinalizer(tear_down)

    params = request.param.copy()
    params['url'] = db_connection_url
    return params


@pytest.fixture(scope="class", params=[
    pytest.param({
        'url': "postgresql://postgres@localhost/%s",
        'admin_db': 'postgres'
    }, marks=pytest.mark.postgres),
    pytest.param({
        'url': 'mysql+pymysql://travis@/%s?charset=utf8',
    }, marks=pytest.mark.mysql),
    pytest.param({
        'url': 'mssql+pyodbc://SA:Password@123@localhost/%s?driver=ODBC+Driver+17+for+SQL+Server',
        'admin_db': 'master'
    }, marks=pytest.mark.mssql)
], ids=['postgres', 'mysql', 'mssql'])
def db_params(request):
    return _db_params(request, TEST_DB)


@pytest.fixture(scope="class", params=[
    {
        'url': "postgresql://postgres@localhost/%s",
        'admin_db': 'postgres'
    },
], ids=['postgres'])
def pg_db_params(request):
    return _db_params(request, 'test_commcare_export_%s' % uuid.uuid4().hex)

