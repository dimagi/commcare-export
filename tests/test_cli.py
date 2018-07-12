# -*- coding: utf-8 -*-
import unittest
from collections import namedtuple
from copy import copy

from mock import mock

from commcare_export.cli import CLI_ARGS, main_with_args
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.writers import JValueTableWriter

CLI_ARGS_BY_NAME = {
    arg.name: arg
    for arg in CLI_ARGS
}


def make_args(project='test', username='test', password='test', **kwargs):
    kwargs['project'] = project
    kwargs['username'] = username
    kwargs['password'] = password

    args_by_name = copy(CLI_ARGS_BY_NAME)
    names = []
    vals = []
    for name, val in kwargs.items():
        args_by_name.pop(name)
        names.append(name)
        vals.append(val)

    for name, arg in args_by_name.items():
        names.append(name)
        vals.append(arg.default)

    return namedtuple('args', names)(*vals)


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

        assert writer.tables.values() == expected
