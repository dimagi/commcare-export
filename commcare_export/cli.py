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

logger = logging.getLogger(__name__)

commcare_hq_aliases = {
    'local': 'http://localhost:8000',
    'prod': 'https://www.commcarehq.org'
}

def main(argv):
    parser = argparse.ArgumentParser('commcare-hq-export', 'Output a customized export of CommCareHQ data.')

    parser.add_argument('--query', help='JSON or Excel query file, or a literal JSON string. If omitted, JSON string is read from stdin.')
    parser.add_argument('--dump-query', default=False, action='store_true')
    parser.add_argument('--commcare-hq', default='prod')
    parser.add_argument('--api-version', default=LATEST_KNOWN_VERSION)
    parser.add_argument('--project', required=True)
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--since')
    parser.add_argument('--start-over', default=False, action='store_true', 
                        help='When saving to a SQL database; the default is to pick up since the last success. This disables that.')
    parser.add_argument('--profile')
    parser.add_argument('--verbose', default=False, action='store_true')
    parser.add_argument('--output-format', default='json', choices=['json', 'csv', 'xls', 'xlsx', 'sql', 'markdown'], help='Output format')
    parser.add_argument('--output', metavar='PATH', default='reports.zip', help='Path to output; defaults to `reports.zip`.')

    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, 
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    else:
        logging.basicConfig(level=logging.WARN,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')

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
    if args.query:
        if os.path.exists(args.query):
            query_file_md5 = misc.digest_file(args.query)
            if os.path.splitext(args.query)[1] in ['.xls', '.xlsx']:
                import openpyxl
                workbook = openpyxl.load_workbook(args.query)
                query = excel_query.compile_workbook(workbook)
            else:
                with io.open(args.query, encoding='utf-8') as fh:
                    query = MiniLinq.from_jvalue(json.loads(fh.read()))
        else:
            query = MiniLinq.from_jvalue(json.loads(args.query))
    else:
        query = MiniLinq.from_jvalue(json.loads(sys.stdin.read()))

    if args.dump_query:
        print(json.dumps(query.to_jvalue(), indent=4))
        exit(0)

    if not args.username:
        args.username = input('Please provide a username: ')

    if not args.password:
        # Windows getpass does not accept unicode
        args.password = getpass.getpass()

    # Build an API client using either the URL provided, or the URL for a known alias
    api_client = CommCareHqClient(url = commcare_hq_aliases.get(args.commcare_hq, args.commcare_hq), 
                                  project = args.project,
                                  version = args.api_version)

    api_client = api_client.authenticated(username=args.username, password=args.password)

    if args.output_format == 'xlsx':
        writer = writers.Excel2007TableWriter(args.output)
    elif args.output_format == 'xls':
        writer = writers.Excel2003TableWriter(args.output)
    elif args.output_format == 'csv':
        writer = writers.CsvTableWriter(args.output)
    elif args.output_format == 'json':
        writer = writers.JValueTableWriter()
    elif args.output_format == 'markdown':
        writer = writers.StreamingMarkdownTableWriter(sys.stdout) 
    elif args.output_format == 'sql':
        writer = writers.SqlTableWriter(args.output) # Output should be a connection URL

        if not args.since and not args.start_over and os.path.exists(args.query):
            connection = sqlalchemy.create_engine(args.output)

            # Grab the current list of tables to see if we have already run & written to it
            metadata = sqlalchemy.MetaData()
            metadata.bind = connection
            metadata.reflect()

            if 'commcare_export_runs' in metadata.tables:
                cursor = connection.execute(sqlalchemy.sql.text('SELECT time_of_run FROM commcare_export_runs WHERE query_file_md5 = :query_file_md5 ORDER BY time_of_run DESC'), query_file_md5=query_file_md5)
                for row in cursor:
                    args.since = row[0]
                    logger.debug('Last successful run was %s', args.since)
                    break
                cursor.close()
            else:
                logger.warn('No successful runs found, and --since not specified: will import ALL data')

    if args.since:
        logger.debug('Starting from %s', args.since)
    env = BuiltInEnv() | CommCareHqEnv(api_client, since=dateutil.parser.parse(args.since) if args.since else None) | JsonPathEnv({}) 
    results = query.eval(env)

    # Assume that if any tables were emitted, that is the idea, otherwise print the output
    if len(list(env.emitted_tables())) > 0:
        with writer:
            for table in env.emitted_tables():
                logger.debug('Writing %s', table['name'])
                writer.write_table(table)

            if args.output_format == 'sql' and os.path.exists(args.query):
                writer.write_table({
                    'name': 'commcare_export_runs',
                    'headings': ['id', 'query_file_name', 'query_file_md5', 'time_of_run'],
                    'rows': [ [uuid.uuid4().hex, args.query, query_file_md5, run_start.isoformat()] ]
                })

        if args.output_format == 'json':
            print(json.dumps(writer.tables, indent=4, default=RepeatableIterator.to_jvalue))
    else:
        print(json.dumps(list(results), indent=4, default=RepeatableIterator.to_jvalue))

def entry_point():
    main(sys.argv[1:])
    
if __name__ == '__main__':
    entry_point()
