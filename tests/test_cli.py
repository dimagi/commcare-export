# -*- coding: utf-8 -*-
import csv
import os
import unittest
from argparse import Namespace
from copy import copy

import pytest
import sqlalchemy
from mock import mock

from commcare_export.checkpoint import CheckpointManager
from commcare_export.cli import CLI_ARGS, main_with_args
from commcare_export.commcare_hq_client import MockCommCareHqClient
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


client = MockCommCareHqClient({
    'form': [
        (
            {'limit': 1000, 'order_by': ['server_modified_on', 'received_on']},
            [
                {'id': 1, 'form': {'name': 'f1', 'case': {'@case_id': 'c1'}}},
                {'id': 2, 'form': {'name': 'f2', 'case': {'@case_id': 'c2'}}},
            ]
        ),
    ],
    'case': [
        (
            {'limit': 1000, 'order_by': 'server_date_modified'},
            [
                {'id': 'case1'},
                {'id': 'case2'},
            ]
        )
    ]
})


class TestCli(unittest.TestCase):

    @mock.patch('commcare_export.cli._get_api_client', return_value=client)
    def test_cli(self, mock_client):
        args = make_args(
            query='tests/008_multiple-tables.xlsx',
            output_format='json',
        )
        writer = JValueTableWriter()
        with mock.patch('commcare_export.cli._get_writer', return_value=writer):
            main_with_args(args)

        expected = [
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

        for table in expected:
            assert writer.tables[table['name']] == table


@pytest.fixture(scope='class')
def writer(pg_db_params):
    return SqlTableWriter(pg_db_params['url'], poolclass=sqlalchemy.pool.NullPool)


@pytest.fixture(scope='class')
def checkpoint_manager(pg_db_params):
    return CheckpointManager(pg_db_params['url'], 'query', '123', 'test', 'hq', poolclass=sqlalchemy.pool.NullPool)


@pytest.mark.dbtest
class TestCLIIntegrationTests(object):
    def test_write_to_sql_with_checkpoints(self, writer, checkpoint_manager, caplog):
        def _pull_data(since, until, batch_size=10):
            args = make_args(
                query='tests/009_integration.xlsx',
                output_format='sql',
                output='',
                username=os.environ['HQ_USERNAME'],
                password=os.environ['HQ_API_KEY'],
                auth_mode='apikey',
                project='corpora',
                batch_size=batch_size,
                since=since,
                until=until
            )

            # have to mock these to override the pool class otherwise they hold the db connection open
            writer_patch = mock.patch('commcare_export.cli._get_writer', return_value=writer)
            checkpoint_patch = mock.patch('commcare_export.cli.get_checkpoint_manager', return_value=checkpoint_manager)
            with writer_patch, checkpoint_patch:
                main_with_args(args)

        with open('tests/009_expected_form_data.csv', 'r') as f:
            reader = csv.reader(f)
            expected_form_data = list(reader)[1:]

        _pull_data('2012-01-01', '2012-08-01')
        self._check_checkpoints(caplog, ['batch', 'batch', 'final'])
        self._check_data(writer, expected_form_data[:16])

        caplog.clear()
        _pull_data(None, '2012-09-01', batch_size=20)
        self._check_data(writer, expected_form_data)
        self._check_checkpoints(caplog, ['batch', 'final'])

        runs = list(writer.engine.execute('SELECT * from commcare_export_runs'))
        assert len(runs) == 2

    def _check_data(self, writer, expected):
        actual = [
            list(row) for row in
            writer.engine.execute("SELECT id, name, received_on, server_modified_on FROM forms")
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
