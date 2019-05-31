from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import argparse
import inspect
import logging
import sys

from commcare_export.cli import CLI_ARGS
from commcare_export.utils import get_checkpoint_manager, confirm, print_runs

EXIT_STATUS_ERROR = 1

logger = logging.getLogger(__name__)


class BaseCommand(object):
    slug = None
    help = None

    @classmethod
    def add_arguments(cls, parser):
        raise NotImplementedError

    def run(self, args):
        raise NotImplementedError


class ListHistoryCommand(BaseCommand):
    slug = 'history'
    help = """List export history. History will be filtered by arguments provided.
    
    This command only applies when exporting to a SQL database. The command lists
    the checkpoints that have been created by the command.
    """

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--limit', default=10, help="Limit the number of export runs to display")
        parser.add_argument('--output', required=True, help='SQL Database URL')
        shared_args = {'project', 'query', 'checkpoint_key', 'commcare_hq'}
        for arg in CLI_ARGS:
            if arg.name in shared_args:
                arg.add_to_parser(parser)

    def run(self, args):
        manager = get_checkpoint_manager(args, require_query=False)
        manager.create_checkpoint_table()

        print("Listing checkpoints (most recent {}):".format(args.limit))
        if args.project:
            print("    project:        {}".format(args.project))
        if args.commcare_hq != 'prod':
            print("    commcare-hq:    {}".format(args.commcare_hq))
        if args.query:
            print("    query filename: {}".format(args.query))
        if manager.key:
            print("    key:            {}".format(manager.key))

        runs = manager.list_checkpoints(args.limit)
        print_runs(runs)


class SetKeyCommand(BaseCommand):
    slug = 'set-checkpoint-key'
    help = """Set the key for a particular checkpoint.

    This command is used to migrate an non-keyed checkpoint to a keyed checkpoint.

    This is useful if you already have a populated export database and do not wish to trigger
    rebuilds after editing the query file.

    For example, you've been running the export tool with query file A.xlsx and have a fully populated
    database. Now you need to add an extra column to the table but only want to populate it with new data.

    What you need to do is update your current checkpoint with a key that you can then use when running
    the command from now on.

      $ commcare-export-utils set-key --project X --query A.xlsx --output [SQL URL] --checkpoint-key my-key

    Now when you run the export tool in future you can use this key:

      $ commcare-export --project X --query A.xlsx --output [SQL URL] --checkpoint-key my-key ...
    """

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--output', required=True, help='SQL Database URL')
        shared_args = {'project', 'query', 'checkpoint_key'}
        for arg in CLI_ARGS:
            if arg.name in shared_args:
                arg.add_to_parser(parser, required=True)
            elif arg.name == 'commcare_hq':
                arg.add_to_parser(parser)

    def run(self, args):
        key = args.checkpoint_key
        manager = get_checkpoint_manager(args)
        manager.create_checkpoint_table()
        run_with_key = manager.list_checkpoints(limit=1)

        if run_with_key:
            print("A checkpoint with that key already exists.")
            return

        manager.key = None
        runs_no_key = manager.get_latest_checkpoints()

        if not runs_no_key:
            print(args)
            print("No checkpoint found with args matching those provided.")
            return

        print_runs(runs_no_key)
        if confirm("Do you want to set the key for this checkpoint to '{}'".format(key)):
            for checkpoint in runs_no_key:
                checkpoint.key = key
                manager.update_checkpoint(checkpoint)

        print("\nUpdated checkpoint:")
        print_runs(runs_no_key)


COMMANDS = [
    ListHistoryCommand,
    SetKeyCommand
]


def main(argv):
    parser = argparse.ArgumentParser('commcare-export-utils')
    subparsers = parser.add_subparsers(dest='command')
    for command_type in COMMANDS:
        sub = subparsers.add_parser(
            command_type.slug,
            help=inspect.cleandoc(command_type.help).splitlines()[0],
            description=inspect.cleandoc(command_type.help),
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        command_type.add_arguments(sub)

    try:
        args = parser.parse_args(argv)
    except UnicodeDecodeError:
        for arg in argv:
            try:
                arg.encode('utf-8')
            except UnicodeDecodeError:
                sys.stderr.write(u"ERROR: Argument '%s' contains unicode characters. "
                                 u"Only ASCII characters are supported.\n" % unicode(arg, 'utf-8'))
        sys.exit(1)

    logging.basicConfig(level=logging.WARN,
                        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')

    exit(main_with_args(args))


def main_with_args(args):
    command = [c for c in COMMANDS if c.slug == args.command][0]
    command().run(args)


def entry_point():
    main(sys.argv[1:])


if __name__ == '__main__':
    entry_point()
