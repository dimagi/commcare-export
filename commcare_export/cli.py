from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import argparse
import sys
import uuid
import json
import getpass
import requests
import hashlib
import pprint
import os.path
import logging
import sqlalchemy
import io
from datetime import datetime

from commcare_export.checkpoint import CheckpointManager
from six.moves import input

import dateutil.parser

from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.env import BuiltInEnv, JsonPathEnv
from commcare_export.minilinq import MiniLinq
from commcare_export.commcare_hq_client import CommCareHqClient, LATEST_KNOWN_VERSION
from commcare_export.commcare_minilinq import CommCareHqEnv
from commcare_export import writers
from commcare_export import excel_query
from commcare_export import misc
from commcare_export.version import __version__

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
    parser.add_argument('--password')
    parser.add_argument('--auth-mode', default='digest', help='Use "session" based auth or "digest" auth.')
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

    args = parser.parse_args(argv)

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
        main_with_args(args)
    finally:
        if args.profile:
            profile.close()
            stats = hotshot.stats.load(args.profile)
            stats.strip_dirs()
            stats.sort_stats('cumulative', 'calls')
            stats.print_stats(100)
            

def main_with_args(args):
    # Grab the timestamp here so that anything that comes in while this runs will be grabbed next time.
    run_start = datetime.utcnow()
    
    # Reads as excel if it is a file name that looks like excel, otherwise reads as JSON, 
    # falling back to parsing arg directly as JSON, and finally parsing stdin as JSON
    missing_value = args.missing_value
    if args.output_format != 'sql' and missing_value is None:
        missing_value = ''

    if args.query:
        if os.path.exists(args.query):
            query_file_md5 = misc.digest_file(args.query)
            if os.path.splitext(args.query)[1] in ['.xls', '.xlsx']:
                import openpyxl
                workbook = openpyxl.load_workbook(args.query)
                query = excel_query.compile_workbook(workbook, missing_value)
            else:
                with io.open(args.query, encoding='utf-8') as fh:
                    query = MiniLinq.from_jvalue(json.loads(fh.read()))
        else:
            print('Query file not found: %s' % args.query)
            exit(1)
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
        exit(0)

    if not args.username:
        args.username = input('Please provide a username: ')

    if not args.password:
        # Windows getpass does not accept unicode
        args.password = getpass.getpass()

    # Build an API client using either the URL provided, or the URL for a known alias
    commcarehq_base_url = commcare_hq_aliases.get(args.commcare_hq, args.commcare_hq)
    api_client = CommCareHqClient(url =commcarehq_base_url,
                                  project = args.project,
                                  version = args.api_version)

    api_client = api_client.authenticated(username=args.username, password=args.password, mode=args.auth_mode)
    checkpoint_manager = None
    if args.output_format == 'xlsx':
        writer = writers.Excel2007TableWriter(args.output)
    elif args.output_format == 'xls':
        writer = writers.Excel2003TableWriter(args.output)
    elif args.output_format == 'csv':
        if not args.output.endswith(".zip"):
            print("WARNING: csv output is a zip file, but "
                  "will be written to %s" % args.output)
            print("Consider appending .zip to the file name to avoid confusion.")
        writer = writers.CsvTableWriter(args.output)
    elif args.output_format == 'json':
        writer = writers.JValueTableWriter()
    elif args.output_format == 'markdown':
        writer = writers.StreamingMarkdownTableWriter(sys.stdout) 
    elif args.output_format == 'sql':
        # Output should be a connection URL
        # Writer had bizarre issues so we use a full connection instead of passing in a URL or engine
        import sqlalchemy
        engine = sqlalchemy.create_engine(args.output)
        is_mysql = 'mysql' in args.output
        collation = 'utf8_bin' if is_mysql else None
        writer = writers.SqlTableWriter(engine.connect(), args.strict_types, collation=collation)
        checkpoint_manager = CheckpointManager(engine.connect(), collation=collation)
        with checkpoint_manager:
            checkpoint_manager.create_checkpoint_table()
        api_client.set_checkpoint_manager(checkpoint_manager, query=args.query, query_md5=query_file_md5)

        if not args.since and not args.start_over and os.path.exists(args.query):
            with checkpoint_manager:
                args.since = checkpoint_manager.get_time_of_last_run(query_file_md5)

            if args.since:
                logger.debug('Last successful run was %s', args.since)
            else:
                logger.warn('No successful runs found, and --since not specified: will import ALL data')

    if args.since:
        logger.debug('Starting from %s', args.since)
    since = dateutil.parser.parse(args.since) if args.since else None
    until = dateutil.parser.parse(args.until) if args.until else None
    env = BuiltInEnv({'commcarehq_base_url': commcarehq_base_url}) | CommCareHqEnv(api_client, since=since, until=until) | JsonPathEnv({})
    results = query.eval(env)

    # Assume that if any tables were emitted, that is the idea, otherwise print the output
    if len(list(env.emitted_tables())) > 0:
        with writer:
            for table in env.emitted_tables():
                logger.debug('Writing %s', table['name'])
                if table['name'] != table['name'].lower():
                    logger.warning(
                        "Caution: Using upper case letters in a "
                        "table name is not advised: {}".format(table['name'])
                    )
                writer.write_table(table)

        if checkpoint_manager and os.path.exists(args.query):
            with checkpoint_manager:
                checkpoint_manager.set_checkpoint(args.query, query_file_md5, run_start, True)

        if args.output_format == 'json':
            print(json.dumps(writer.tables, indent=4, default=RepeatableIterator.to_jvalue))
    else:
        print(json.dumps(list(results), indent=4, default=RepeatableIterator.to_jvalue))

def entry_point():
    main(sys.argv[1:])
    
if __name__ == '__main__':
    entry_point()
