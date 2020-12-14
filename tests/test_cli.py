# -*- coding: utf-8 -*-
import csv342 as csv
import os
import re
import unittest
from argparse import Namespace
from copy import copy

import pytest
import sqlalchemy
from mock import mock

from commcare_export.checkpoint import CheckpointManager
from commcare_export.cli import CLI_ARGS, EXIT_STATUS_ERROR, main_with_args
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.specs import TableSpec
from commcare_export.writers import JValueTableWriter, SqlTableWriter

CLI_ARGS_BY_NAME = {
    arg.name: arg
    for arg in CLI_ARGS
}

try:
    from itertools import izip_longest as zip_longest
except ImportError:
    # PY 3
    from itertools import zip_longest


DEFAULT_BATCH_SIZE = 200


def make_args(project='test', username='test', password='test', **kwargs):
    kwargs['project'] = project
    kwargs['username'] = username
    kwargs['password'] = password

    args_by_name = copy(CLI_ARGS_BY_NAME)
    namespace = Namespace()
    for name, val in kwargs.items():
        args_by_name.pop(name)
        setattr(namespace, name, val)

    for name, arg in args_by_name.items():
        setattr(namespace, name, arg.default)

    return namespace


def mock_hq_client(include_parent):
    return MockCommCareHqClient({
        'form': [
            (
                {'limit': DEFAULT_BATCH_SIZE, 'order_by': ['server_modified_on', 'received_on']},
                [
                    {'id': 1, 'form': {'name': 'f1', 'case': {'@case_id': 'c1'}},
                     'metadata': {'userID': 'id1'}},
                    {'id': 2, 'form': {'name': 'f2', 'case': {'@case_id': 'c2'}},
                     'metadata': {'userID': 'id2'}},
                ]
            ),
        ],
        'case': [
            (
                {'limit': DEFAULT_BATCH_SIZE, 'order_by': 'server_date_modified'},
                [
                    {'id': 'case1'},
                    {'id': 'case2'},
                ]
            )
        ],
        'user': [
            (
                {'limit': DEFAULT_BATCH_SIZE},
                [
                    {'id': 'id1', 'email': 'em1', 'first_name': 'fn1',
                     'last_name': 'ln1',
                     'user_data': {'commcare_location_id': 'lid1',
                                   'commcare_location_ids': ['lid1', 'lid2'],
                                   'commcare_project': 'p1'},
                     'username': 'u1'},
                    {'id': 'id2', 'default_phone_number': 'pn2', 'email': 'em2',
                     'first_name': 'fn2', 'last_name': 'ln2',
                     'resource_uri': 'ru0',
                     'user_data': {'commcare_location_id': 'lid2',
                                   'commcare_project': 'p2'},
                     'username': 'u2'}
                ]
            )
        ],
        'location_type': [
            (
                {'limit': DEFAULT_BATCH_SIZE},
                [
                    {'administrative': True, 'code': 'hq', 'domain': 'd1', 'id': 1,
                     'name': 'HQ', 'parent': None, 'resource_uri': 'lt1',
                     'shares_cases': False, 'view_descendants': True},
                    {'administrative': False, 'code': 'local', 'domain': 'd1',
                     'id': 2, 'name': 'Local',
                     'parent': 'lt1', 'resource_uri': 'lt2',
                     'shares_cases': True, 'view_descendants': True}
                ]
            )
        ],
        'location': [
            (
                {'limit': DEFAULT_BATCH_SIZE},
                [
                    {'id': 'id1', 'created_at': '2020-04-01T21:57:26.403053',
                     'domain': 'd1', 'external_id': 'eid1',
                     'last_modified': '2020-04-01T21:58:23.88343',
                     'latitude': '11.2', 'location_data': {'p1': 'ld1'},
                     'location_id': 'lid1', 'location_type': 'lt1',
                     'longitude': '-20.5', 'name': 'n1',
                     'resource_uri': 'ru1', 'site_code': 'sc1'},
                    {'id': 'id2', 'created_at': '2020-04-01T21:58:47.627371',
                     'domain': 'd2', 'last_modified': '2020-04-01T21:59:16.018411',
                     'latitude': '-56.3', 'location_data': {'p1': 'ld2'},
                     'location_id': 'lid2', 'location_type': 'lt2',
                     'longitude': '18.7', 'name': 'n2',
                     'parent': 'ru1' if include_parent else None,
                     'resource_uri': 'ru2', 'site_code': 'sc2'}
                ]
            )
        ],
    })


EXPECTED_MULTIPLE_TABLES_RESULTS = [
    {
        "name": "Forms",
        "headings": ["id", "name"],
        "rows": [
            ["1", "f1"],
            ["2", "f2"]
        ],
    },
    {
        "name": "Other cases",
        "headings": ["id"],
        "rows": [
            ["case1"],
            ["case2"]
        ],
    },
    {
        "name": "Cases",
        "headings": ["case_id"],
        "rows": [
            ["c1"],
            ["c2"]
        ],
    }
]

EXPECTED_USERS_RESULTS = [
    {
        "name": "commcare_users",
        "headings": [
            "id",
            "default_phone_number",
            "email",
            "first_name",
            "groups",
            "last_name",
            "phone_numbers",
            "resource_uri",
            "commcare_location_id",
            "commcare_location_ids",
            "commcare_primary_case_sharing_id",
            "commcare_project",
            "username"
        ],
        "rows": [
            ["id1", None, "em1", "fn1", None, "ln1", None, None, "lid1",
             "lid1,lid2", None, "p1", "u1"],
            ["id2", "pn2", "em2", "fn2", None, "ln2", None, "ru0", "lid2",
             None, None, "p2", "u2"]
        ]
    }
]


def get_expected_locations_results(include_parent):
    return [
        {
            "name": "commcare_locations",
            "headings": [
                "id",
                "created_at",
                "domain",
                "external_id",
                "last_modified",
                "latitude",
                "location_data",
                "location_id",
                "location_type",
                "longitude",
                "name",
                "parent",
                "resource_uri",
                "site_code",
                "location_type_administrative",
                "location_type_code",
                "location_type_name",
                "location_type_parent",
                "local",
                "hq"
            ],
            "rows": [
                ["id1", "2020-04-01 21:57:26", "d1", "eid1",
                 "2020-04-01 21:58:23", "11.2", '{"p1": "ld1", "id": "id1.location_data"}', "lid1", "lt1",
                 "-20.5", "n1", None, "ru1", "sc1", True, "hq", "HQ", None,
                 None, "lid1"],
                ["id2", "2020-04-01 21:58:47", "d2", None,
                 "2020-04-01 21:59:16", "-56.3", '{"p1": "ld2", "id": "id2.location_data"}', "lid2", "lt2",
                 "18.7", "n2", ("ru1" if include_parent else None), "ru2",
                 "sc2", False, "local", "Local", "lt1",
                 "lid2", ("lid1" if include_parent else None)]
            ]
        }
       ]


class TestCli(unittest.TestCase):

    def _test_cli(self, args, expected):
        writer = JValueTableWriter()
        with mock.patch('commcare_export.cli._get_writer', return_value=writer):
            main_with_args(args)

        for table in expected:
            assert writer.tables[table['name']] == TableSpec(**table)


    @mock.patch('commcare_export.cli._get_api_client', return_value=mock_hq_client(True))
    def test_cli(self, mock_client):
        args = make_args(
            query='tests/008_multiple-tables.xlsx',
            output_format='json'
        )
        self._test_cli(args, EXPECTED_MULTIPLE_TABLES_RESULTS)

    @mock.patch('commcare_export.cli._get_api_client', return_value=mock_hq_client(True))
    def test_cli_just_users(self, mock_client):
        args = make_args(
            output_format='json',
            users=True
        )
        self._test_cli(args, EXPECTED_USERS_RESULTS)

    @mock.patch('commcare_export.cli._get_api_client', return_value=mock_hq_client(True))
    def test_cli_table_plus_users(self, mock_client):
        args = make_args(
            query='tests/008_multiple-tables.xlsx',
            output_format='json',
            users=True
        )
        self._test_cli(args, EXPECTED_MULTIPLE_TABLES_RESULTS +
                       EXPECTED_USERS_RESULTS)

    @mock.patch('commcare_export.cli._get_api_client', return_value=mock_hq_client(True))
    def test_cli_just_locations(self, mock_client):
        args = make_args(
            output_format='json',
            locations=True
        )
        self._test_cli(args, get_expected_locations_results(True))

    @mock.patch('commcare_export.cli._get_api_client', return_value=mock_hq_client(False))
    def test_cli_locations_without_parents(self, mock_client):
        args = make_args(
            output_format='json',
            locations=True
        )
        self._test_cli(args, get_expected_locations_results(False))

    @mock.patch('commcare_export.cli._get_api_client', return_value=mock_hq_client(True))
    def test_cli_table_plus_locations(self, mock_client):
        args = make_args(
            query='tests/008_multiple-tables.xlsx',
            output_format='json',
            locations=True
        )
        self._test_cli(args, EXPECTED_MULTIPLE_TABLES_RESULTS +
                       get_expected_locations_results(True))


@pytest.fixture(scope='class')
def writer(pg_db_params):
    return SqlTableWriter(pg_db_params['url'], poolclass=sqlalchemy.pool.NullPool)


@pytest.fixture(scope='class')
def checkpoint_manager(pg_db_params):
    cm = CheckpointManager(pg_db_params['url'], 'query', '123', 'test', 'hq', poolclass=sqlalchemy.pool.NullPool)
    cm.create_checkpoint_table()
    return cm


def _pull_data(writer, checkpoint_manager, query, since, until, batch_size=10):
    args = make_args(
        query=query,
        output_format='sql',
        output='',
        username=os.environ['HQ_USERNAME'],
        password=os.environ['HQ_API_KEY'],
        auth_mode='apikey',
        project='corpora',
        batch_size=batch_size,
        since=since,
        until=until,
    )

    # set this so that it get's written to the checkpoints
    checkpoint_manager.query = query

    # have to mock these to override the pool class otherwise they hold the db connection open
    writer_patch = mock.patch('commcare_export.cli._get_writer', return_value=writer)
    checkpoint_patch = mock.patch('commcare_export.cli._get_checkpoint_manager', return_value=checkpoint_manager)
    with writer_patch, checkpoint_patch:
        main_with_args(args)


@pytest.mark.dbtest
class TestCLIIntegrationTests(object):
    def test_write_to_sql_with_checkpoints(self, writer, checkpoint_manager, caplog):
        with open('tests/009_expected_form_data.csv', 'r') as f:
            reader = csv.reader(f)
            expected_form_data = list(reader)[1:]

        _pull_data(writer, checkpoint_manager, 'tests/009_integration.xlsx', '2012-01-01', '2012-08-01')
        self._check_checkpoints(caplog, ['forms', 'batch', 'final'])
        self._check_data(writer, expected_form_data[:16], 'forms')

        caplog.clear()
        _pull_data(writer, checkpoint_manager, 'tests/009_integration.xlsx', None, '2012-09-01', batch_size=8)
        self._check_data(writer, expected_form_data, 'forms')
        self._check_checkpoints(caplog, ['forms', 'batch', 'final'])

        runs = list(writer.engine.execute(
            'SELECT * from commcare_export_runs where query_file_name = %s', 'tests/009_integration.xlsx'
        ))
        assert len(runs) == 2, runs

    def test_write_to_sql_with_checkpoints_multiple_tables(self, writer, checkpoint_manager, caplog):
        with open('tests/009b_expected_form_1_data.csv', 'r') as f:
            reader = csv.reader(f)
            expected_form_1_data = list(reader)[1:]

        with open('tests/009b_expected_form_2_data.csv', 'r') as f:
            reader = csv.reader(f)
            expected_form_2_data = list(reader)[1:]

        _pull_data(writer, checkpoint_manager, 'tests/009b_integration_multiple.xlsx', None, '2012-05-01')
        self._check_checkpoints(caplog, ['forms_1', 'final', 'forms_2', 'final'])
        self._check_checkpoints(caplog, ['forms_1', 'forms_1', 'forms_2', 'forms_2'])
        self._check_data(writer, expected_form_1_data, 'forms_1')
        self._check_data(writer, expected_form_2_data, 'forms_2')

        runs = list(writer.engine.execute(
            'SELECT table_name, since_param from commcare_export_runs where query_file_name = %s',
            'tests/009b_integration_multiple.xlsx'
        ))
        assert {r[0]: r[1] for r in runs} == {
            'forms_1': '2012-04-27T10:05:55',
            'forms_2': '2012-04-27T14:23:50'
        }

    def _check_data(self, writer, expected, table_name):
        actual = [
            list(row) for row in
            writer.engine.execute("SELECT id, name, received_on, server_modified_on FROM {}".format(table_name))
        ]

        message = ''
        if actual != expected:
            message += 'Data not equal to expected:\n'
            if len(actual) != len(expected):
                message += '    {} rows compared to {} expected\n'.format(len(actual), len(expected))
            message += 'Diff:\n'
            for i, rows in enumerate(zip_longest(actual, expected)):
                if rows[0] != rows[1]:
                    message += '{}: {} != {}\n'.format(i, rows[0], rows[1])
            assert actual == expected, message

    def _check_checkpoints(self, caplog, expected):
        # Depends on the logging in the CheckpointManager._set_checkpoint method
        log_messages = [
            record[2] for record in caplog.record_tuples
            if record[0] == 'commcare_export.checkpoint'
        ]
        fail = False
        message = ''
        for i, items in enumerate(zip_longest(expected, log_messages)):
            if not items[0] or not items[1] or items[0] not in items[1]:
                message += 'X {}: {} not in {}\n'.format(i, items[0], items[1])
                fail = True
            else:
                message += '✓ {}: {} in {}\n'.format(i, items[0], items[1])
        assert not fail, 'Checkpoint comparison failed:\n' + message


# Conflicting types for 'count' will cause errors when inserting into database.
CONFLICTING_TYPES_CLIENT = MockCommCareHqClient({
    'form': [
        (
            {'limit': DEFAULT_BATCH_SIZE, 'order_by': ['server_modified_on', 'received_on']},
            [
                {'id': 1, 'form': {'name': 'n1', 'count': 10}},
                {'id': 2, 'form': {'name': 'f2', 'count': 'abc'}}
            ]
        ),
    ],
})


@pytest.fixture(scope='class')
def strict_writer(db_params):
    return SqlTableWriter(db_params['url'], poolclass=sqlalchemy.pool.NullPool, strict_types=True)


@pytest.fixture(scope='class')
def all_db_checkpoint_manager(db_params):
    cm = CheckpointManager(db_params['url'], 'query', '123', 'test', 'hq', poolclass=sqlalchemy.pool.NullPool)
    cm.create_checkpoint_table()
    return cm


def _pull_mock_data(writer, checkpoint_manager, api_client, query):
    args = make_args(
        query=query,
        output_format='sql',
    )

    # set this so that it get's written to the checkpoints
    checkpoint_manager.query = query

    # have to mock these to override the pool class otherwise they hold the db connection open
    api_client_patch = mock.patch('commcare_export.cli._get_api_client',
                                  return_value=api_client)
    writer_patch = mock.patch('commcare_export.cli._get_writer', return_value=writer)
    checkpoint_patch = mock.patch('commcare_export.cli._get_checkpoint_manager', return_value=checkpoint_manager)
    with api_client_patch, writer_patch, checkpoint_patch:
        return main_with_args(args)


@pytest.mark.dbtest
class TestCLIWithDatabaseErrors(object):
    def test_cli_database_error(self, strict_writer, all_db_checkpoint_manager, capfd):
        _pull_mock_data(strict_writer, all_db_checkpoint_manager, CONFLICTING_TYPES_CLIENT, 'tests/013_ConflictingTypes.xlsx')
        out, err = capfd.readouterr()

        expected_re = re.compile('Stopping because of database error')
        assert re.search(expected_re, out)


# An input where missing fields should be added due to declared data types.
DATA_TYPES_CLIENT = MockCommCareHqClient({
    'form': [
        (
            {'limit': DEFAULT_BATCH_SIZE, 'order_by': ['server_modified_on', 'received_on']},
            [
                {'id': 1, 'form': {}},
                {'id': 2, 'form': {}}
            ]
        ),
    ],
})


@pytest.mark.dbtest
class TestCLIWithDataTypes(object):
    def test_cli_data_types_add_columns(self, strict_writer, all_db_checkpoint_manager, capfd):
        _pull_mock_data(strict_writer, all_db_checkpoint_manager, CONFLICTING_TYPES_CLIENT, 'tests/014_ExportWithDataTypes.xlsx')

        metadata = sqlalchemy.schema.MetaData(bind=strict_writer.engine,
                                              reflect=True)

        cols = metadata.tables['forms'].c
        assert sorted([c.name for c in cols]) == sorted([u'id', u'a_bool', u'an_int', u'a_date', u'a_datetime', u'a_text'])

        # We intentionally don't check the types because SQLAlchemy doesn't
        # support type comparison, and even if we convert to strings, the
        # values are backend specific.

        values = [
            list(row) for row in
            strict_writer.engine.execute('SELECT * FROM forms')
        ]

        assert values == [['1', None, None, None, None, None],
                          ['2', None, None, None, None, None]]
