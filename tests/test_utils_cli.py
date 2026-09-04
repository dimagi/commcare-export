import argparse

import pytest

from commcare_export.utils_cli import ListHistoryCommand, SetKeyCommand


def make_parser(command):
    parser = argparse.ArgumentParser()
    command.add_arguments(parser)
    return parser


@pytest.mark.parametrize('command', [ListHistoryCommand, SetKeyCommand])
def test_commands_accept_a_checkpoint_database_url_without_output(command):
    args = make_parser(command).parse_args([
        '--checkpoint-database-url', 'sqlite:///checkpoints.db',
        '--project', 'p', '--query', 'q.xlsx', '--checkpoint-key', 'k',
    ])
    assert args.checkpoint_database_url == 'sqlite:///checkpoints.db'
    assert args.output is None


@pytest.mark.parametrize('command', [ListHistoryCommand, SetKeyCommand])
def test_commands_reject_both_database_arguments(command):
    with pytest.raises(SystemExit):
        make_parser(command).parse_args([
            '--output', 'postgresql://localhost/db',
            '--checkpoint-database-url', 'sqlite:///checkpoints.db',
            '--project', 'p', '--query', 'q.xlsx', '--checkpoint-key', 'k',
        ])
