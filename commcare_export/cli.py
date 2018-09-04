from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import argparse
import getpass
import io
import json
import logging
import os.path
import sys

import dateutil.parser
import requests
from six.moves import input

from commcare_export import excel_query
from commcare_export import writers
from commcare_export.utils import get_checkpoint_manager
from commcare_export.commcare_hq_client import CommCareHqClient, LATEST_KNOWN_VERSION
from commcare_export.commcare_minilinq import CommCareHqEnv
from commcare_export.env import BuiltInEnv, JsonPathEnv, EmitterEnv
from commcare_export.exceptions import LongFieldsException
from commcare_export.minilinq import MiniLinq
from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.version import __version__

EXIT_STATUS_ERROR = 1

logger = logging.getLogger(__name__)

commcare_hq_aliases = {
    'local': 'http://localhost:8000',
    'prod': 'https://www.commcarehq.org'
}


class Argument(object):
    def __init__(self, name, *args, **kwargs):
        self.name = name.replace('-', '_')
        self._args = ['--{}'.format(name)] + list(args)
        self._kwargs = kwargs

    @property
    def default(self):
        return self._kwargs.get('default')

    def add_to_parser(self, parser, **additional_kwargs):
        additional_kwargs.update(self._kwargs)
        parser.add_argument(*self._args, **additional_kwargs)


CLI_ARGS = [
        Argument('version', default=False, action='store_true',
                 help='Print the current version of the commcare-export tool.'),
        Argument('query', help='JSON or Excel query file. If omitted, JSON string is read from stdin.'),
        Argument('dump-query', default=False, action='store_true'),
        Argument('commcare-hq', default='prod',
                 help='Base url for the CommCare HQ instance e.g. https://www.commcarehq.org'),
        Argument('api-version', default=LATEST_KNOWN_VERSION),
        Argument('project'),
        Argument('username'),
        Argument('password', help='Enter password, or if using apikey auth-mode, enter the api key.'),
        Argument('auth-mode', default='password', choices=['password', 'apikey'],
                 help='Use "digest" auth, or "apikey" auth (for two factor enabled domains).'),
        Argument('since', help='Export all data after this date. Format YYYY-MM-DD or YYYY-MM-DDTHH:mm:SS'),
        Argument('until', help='Export all data up until this date. Format YYYY-MM-DD or YYYY-MM-DDTHH:mm:SS'),
        Argument('start-over', default=False, action='store_true',
                 help='When saving to a SQL database; the default is to pick up since the last success. This disables that.'),
        Argument('profile'),
        Argument('verbose', default=False, action='store_true'),
        Argument('output-format', default='json', choices=['json', 'csv', 'xls', 'xlsx', 'sql', 'markdown'],
                 help='Output format'),
        Argument('output', metavar='PATH', default='reports.zip', help='Path to output; defaults to `reports.zip`.'),
        Argument('strict-types', default=False, action='store_true',
                 help="When saving to a SQL database don't allow changing column types once they are created."),
        Argument('missing-value', default=None, help="Value to use when a field is missing from the form / case."),
        Argument('batch-size', default=1000, help="Number of records to process per batch."),
        Argument('checkpoint-key', help="Use this key for all checkpoints instead of the query file MD5 hash "
                                        "in order to prevent table rebuilds after a query file has been edited."),
    ]


def main(argv):
    parser = argparse.ArgumentParser('commcare-export', 'Output a customized export of CommCareHQ data.')
    for arg in CLI_ARGS:
        arg.add_to_parser(parser)

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

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, 
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    else:
        logging.basicConfig(level=logging.WARN,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')

    logging.getLogger('alembic').setLevel(logging.WARN)
    logging.getLogger('backoff').setLevel(logging.FATAL)

    if args.version:
        print('commcare-export version {}'.format(__version__))
        exit(0)

    if not args.project:
        print('commcare-export: error: argument --project is required')
        exit(1)

    if args.profile:
        # hotshot is gone in Python 3
        import hotshot
        import hotshot.stats
        profile = hotshot.Profile(args.profile)
        profile.start()

    try:
        exit(main_with_args(args))
    finally:
        if args.profile:
            profile.close()
            stats = hotshot.stats.load(args.profile)
            stats.strip_dirs()
            stats.sort_stats('cumulative', 'calls')
            stats.print_stats(100)


def _get_query(args, writer):
    # Reads as excel if it is a file name that looks like excel, otherwise reads as JSON,
    # falling back to parsing arg directly as JSON, and finally parsing stdin as JSON
    if args.query:
        return _get_query_from_file(
            args.query,
            args.missing_value,
            writer.supports_multi_table_write,
            writer.max_column_length,
        )
    else:
        try:
            return MiniLinq.from_jvalue(json.loads(sys.stdin.read()))
        except Exception as e:
            raise Exception(
                "Failure reading query from console input. "
                "Try using the '--query' parameter to pass your query as an Excel file", e
            )

def _get_query_from_file(query_arg, missing_value, combine_emits, max_column_length):
    if os.path.exists(query_arg):
        if os.path.splitext(query_arg)[1] in ['.xls', '.xlsx']:
            import openpyxl
            workbook = openpyxl.load_workbook(query_arg)
            return excel_query.get_queries_from_excel(workbook, missing_value, combine_emits, max_column_length)
        else:
            with io.open(query_arg, encoding='utf-8') as fh:
                return MiniLinq.from_jvalue(json.loads(fh.read()))


def _get_writer(output_format, output, strict_types):
    if output_format == 'xlsx':
        return writers.Excel2007TableWriter(output)
    elif output_format == 'xls':
        return writers.Excel2003TableWriter(output)
    elif output_format == 'csv':
        if not output.endswith(".zip"):
            print("WARNING: csv output is a zip file, but "
                  "will be written to %s" % output)
            print("Consider appending .zip to the file name to avoid confusion.")
        return writers.CsvTableWriter(output)
    elif output_format == 'json':
        return writers.JValueTableWriter()
    elif output_format == 'markdown':
        return writers.StreamingMarkdownTableWriter(sys.stdout)
    elif output_format == 'sql':
        # Output should be a connection URL
        # Writer had bizarre issues so we use a full connection instead of passing in a URL or engine
        return writers.SqlTableWriter(output, strict_types)
    else:
        raise Exception("Unknown output format: {}".format(output_format))


def get_date_params(args, checkpoint_manager):
    if args.start_over and checkpoint_manager:
        logger.warn('Ignoring all checkpoints and re-fetching all data from CommCare.')

    if not args.since and not args.start_over and checkpoint_manager:
        args.since = checkpoint_manager.get_time_of_last_checkpoint()

        if args.since:
            logger.debug('Last successful checkpoint was %s', args.since)
        else:
            logger.warn('No successful runs found, and --since not specified: will import ALL data')

    since = dateutil.parser.parse(args.since) if args.since else None
    until = dateutil.parser.parse(args.until) if args.until else None
    return since, until


def _get_api_client(args, checkpoint_manager, commcarehq_base_url):
    return CommCareHqClient(
        url=commcarehq_base_url,
        project=args.project,
        username=args.username,
        password=args.password,
        auth_mode=args.auth_mode,
        version=args.api_version,
        checkpoint_manager=checkpoint_manager
    )


def _get_checkpoint_manager(args):
    if not os.path.exists(args.query):
        logger.warning("Checkpointing disabled for non file-based query")
    elif args.since or args.until:
        logger.warning("Checkpointing disabled when using '--since' or '--until'")
    else:
        checkpoint_manager = get_checkpoint_manager(args)
        checkpoint_manager.create_checkpoint_table()
        return checkpoint_manager


def main_with_args(args):
    writer = _get_writer(args.output_format, args.output, args.strict_types)

    try:
        query = _get_query(args, writer)
    except LongFieldsException as e:
        print(e.message)
        return EXIT_STATUS_ERROR

    if not query:
        print('Query file not found: %s' % args.query)
        return EXIT_STATUS_ERROR

    if args.dump_query:
        print(json.dumps(query.to_jvalue(), indent=4))
        return

    checkpoint_manager = None
    if writer.support_checkpoints:
        checkpoint_manager = _get_checkpoint_manager(args)

    if not args.username:
        args.username = input('Please provide a username: ')

    if not args.password:
        # Windows getpass does not accept unicode
        args.password = getpass.getpass()

    commcarehq_base_url = commcare_hq_aliases.get(args.commcare_hq, args.commcare_hq)
    api_client = _get_api_client(args, checkpoint_manager, commcarehq_base_url)

    since, until = get_date_params(args, checkpoint_manager)
    if since:
        logger.debug('Starting from %s', args.since)
    env = (
            BuiltInEnv({'commcarehq_base_url': commcarehq_base_url})
            | CommCareHqEnv(api_client, since=since, until=until, page_size=args.batch_size)
            | JsonPathEnv({})
            | EmitterEnv(writer)
    )

    with env:
        try:
            lazy_result = query.eval(env)
            if lazy_result is not None:
                # evaluate lazy results
                for r in lazy_result:
                    list(r) if r else r
        except requests.exceptions.RequestException as e:
            if e.response.status_code == 401:
                print("\nAuthentication failed. Please check your credentials.")
                return
            else:
                raise


    if checkpoint_manager:
        checkpoint_manager.set_final_checkpoint()

    if args.output_format == 'json':
        print(json.dumps(list(writer.tables.values()), indent=4, default=RepeatableIterator.to_jvalue))


def entry_point():
    main(sys.argv[1:])


if __name__ == '__main__':
    entry_point()
