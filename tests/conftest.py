import logging
import os
import uuid

import sqlalchemy
from sqlalchemy.exc import DBAPIError

import pytest

TEST_DB = 'test_commcare_export_%s' % uuid.uuid4().hex

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler())


def pytest_configure(config):
    config.addinivalue_line("markers", "dbtest: mark test that requires database access")
    config.addinivalue_line("markers", "postgres: mark PostgreSQL test")
    config.addinivalue_line("markers", "mysql: mark MySQL test")
    config.addinivalue_line("markers", "mssql: mark MSSQL test")


def _db_params(request, db_name):
    db_url = request.param['url']
    sudo_engine = sqlalchemy.create_engine(db_url % request.param.get('admin_db', ''), poolclass=sqlalchemy.pool.NullPool)
    db_connection_url = db_url % db_name

    def tear_down():
        with sudo_engine.connect() as conn:
            if 'postgres' in db_url:
                conn.execute('rollback')
            if 'mssql' in db_url:
                conn.connection.connection.autocommit = True
            conn.execute('drop database if exists %s' % db_name)

    try:
        with sqlalchemy.create_engine(db_connection_url).connect():
            pass
    except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.InternalError, DBAPIError):
        with sudo_engine.connect() as conn:
            if 'postgres' in db_url:
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


postgres_base = os.environ.get('POSTGRES_URL', 'postgresql://postgres@localhost/')
mysql_base = os.environ.get('MYSQL_URL', 'mysql+pymysql://travis@/')
mssql_base = os.environ.get('MSSQL_URL', 'mssql+pyodbc://SA:Password-123@localhost/')


@pytest.fixture(scope="class", params=[
    pytest.param({
        'url': "{}%s".format(postgres_base),
        'admin_db': 'postgres'
    }, marks=pytest.mark.postgres),
    pytest.param({
        'url': '{}%s?charset=utf8mb4'.format(mysql_base),
    }, marks=pytest.mark.mysql),
    pytest.param({
        'url': '{}%s?driver=ODBC+Driver+17+for+SQL+Server'.format(mssql_base),
        'admin_db': 'master'
    }, marks=pytest.mark.mssql)
], ids=['postgres', 'mysql', 'mssql'])
def db_params(request):
    return _db_params(request, TEST_DB)


@pytest.fixture(scope="class", params=[
    {
        'url': "{}%s".format(postgres_base),
        'admin_db': 'postgres'
    },
], ids=['postgres'])
def pg_db_params(request):
    return _db_params(request, 'test_commcare_export_%s' % uuid.uuid4().hex)
