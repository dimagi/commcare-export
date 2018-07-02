from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import argparse
import getpass
import io
import json
import logging
import os.path
import sys
from datetime import datetime

import dateutil.parser
from six.moves import input

from commcare_export import excel_query
from commcare_export import misc
from commcare_export import writers
from commcare_export.checkpoint import CheckpointManager
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

def main(argv):
    parser = argparse.ArgumentParser('commcare-export', 'Output a customized export of CommCareHQ data.')

    parser.add_argument('--version', default=False, action='store_true', help='Print the current version of the commcare-export tool.')
    parser.add_argument('--query', help='JSON or Excel query file. If omitted, JSON string is read from stdin.')
    parser.add_argument('--dump-query', default=False, action='store_true')
    parser.add_argument('--commcare-hq', default='prod', help='Base url for the CommCare HQ instance e.g. https://www.commcarehq.org')
    parser.add_argument('--api-version', default=LATEST_KNOWN_VERSION)
    parser.add_argument('--project')
    parser.add_argument('--username')
    parser.add_argument('--password', help='Enter password, or if using apikey auth-mode, enter the api key.')
    parser.add_argument('--auth-mode', default='digest', choices=['digest', 'apikey'],
                        help='Use "digest" auth, or "apikey" auth (for two factor enabled domains).')
    parser.add_argument('--since', help='Export all data after this date. Format YYYY-MM-DD or YYYY-MM-DDTHH:mm:SS')
    parser.add_argument('--until', help='Export all data up until this date. Format YYYY-MM-DD or YYYY-MM-DDTHH:mm:SS')
    parser.add_argument('--start-over', default=False, action='store_true',
                        help='When saving to a SQL database; the default is to pick up since the last success. This disables that.')
    parser.add_argument('--profile')
    parser.add_argument('--verbose', default=False, action='store_true')
    parser.add_argument('--output-format', default='json', choices=['json', 'csv', 'xls', 'xlsx', 'sql', 'markdown'], help='Output format')
    parser.add_argument('--output', metavar='PATH', default='reports.zip', help='Path to output; defaults to `reports.zip`.')
    parser.add_argument('--strict-types', default=False, action='store_true', help="When saving to a SQL database don't allow changing column types once they are created.")
    parser.add_argument('--missing-value', default=None, help="Value to use when a field is missing from the form / case.")

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


def _get_query(query_arg, missing_value, combine_emits, max_column_length):
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


def main_with_args(args):
    # Grab the timestamp here so that anything that comes in while this runs will be grabbed next time.
    run_start = datetime.utcnow()

    writer = _get_writer(args.output_format, args.output, args.strict_types)
    
    # Reads as excel if it is a file name that looks like excel, otherwise reads as JSON, 
    # falling back to parsing arg directly as JSON, and finally parsing stdin as JSON
    if args.query:
        try:
            query = _get_query(
                args.query,
                args.missing_value,
                writer.supports_multi_table_write,
                writer.max_column_length,
            )
        except LongFieldsException as e:
            print(e.message)
            return EXIT_STATUS_ERROR

        if not query:
            print('Query file not found: %s' % args.query)
            return EXIT_STATUS_ERROR
    else:
        try:
            query = MiniLinq.from_jvalue(json.loads(sys.stdin.read()))
        except Exception as e:
            raise Exception(
                "Failure reading query from console input. "
                "Try using the '--query' parameter to pass your query as an Excel file", e
            )

    if args.dump_query:
        print(json.dumps(query.to_jvalue(), indent=4))
        return

    query_file_md5 = misc.digest_file(args.query)

    checkpoint_manager = None
    if writer.support_checkpoints:
        checkpoint_manager = CheckpointManager(args.output, args.query, query_file_md5)
        with checkpoint_manager:
            checkpoint_manager.create_checkpoint_table()

        if not args.since and not args.start_over and os.path.exists(args.query):
            with checkpoint_manager:
                args.since = checkpoint_manager.get_time_of_last_run()

            if args.since:
                logger.debug('Last successful run was %s', args.since)
            else:
                logger.warn('No successful runs found, and --since not specified: will import ALL data')

    if not args.username:
        args.username = input('Please provide a username: ')

    if not args.password:
        # Windows getpass does not accept unicode
        args.password = getpass.getpass()

    # Build an API client using either the URL provided, or the URL for a known alias
    commcarehq_base_url = commcare_hq_aliases.get(args.commcare_hq, args.commcare_hq)
    api_client = CommCareHqClient(
        url=commcarehq_base_url,
        project=args.project,
        version=args.api_version,
        checkpoint_manager=checkpoint_manager
    )

    api_client = api_client.authenticated(username=args.username, password=args.password, mode=args.auth_mode)

    if args.since:
        logger.debug('Starting from %s', args.since)
    since = dateutil.parser.parse(args.since) if args.since else None
    until = dateutil.parser.parse(args.until) if args.until else None
    env = BuiltInEnv({'commcarehq_base_url': commcarehq_base_url}) | CommCareHqEnv(api_client, since=since, until=until) | JsonPathEnv({}) | EmitterEnv(writer)

    with env:
        results = list(query.eval(env))  # evaluate the result

    if args.output_format == 'json':
        print(json.dumps(list(writer.tables.values()), indent=4, default=RepeatableIterator.to_jvalue))

    if env.has_emitted_tables():
        if checkpoint_manager and os.path.exists(args.query):
            with checkpoint_manager:
                checkpoint_manager.set_checkpoint(run_start, True)
    else:
        # If no tables were emitted just print the output
        print(json.dumps(results, indent=4, default=RepeatableIterator.to_jvalue))


def entry_point():
    main(sys.argv[1:])
    
if __name__ == '__main__':
    entry_point()
