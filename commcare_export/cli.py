import sys
import argparse
import json
import getpass
import requests
import pprint
import os.path

from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.env import BuiltInEnv, JsonPathEnv
from commcare_export.minilinq import MiniLinq
from commcare_export.commcare_hq_client import CommCareHqClient, LATEST_KNOWN_VERSION
from commcare_export.commcare_minilinq import CommCareHqEnv
from commcare_export import writers
from commcare_export import excel_query

commcare_hq_aliases = {
    'local': 'http://localhost:8000',
    'prod': 'https://www.commcare-hq.org'
}

def main(argv):
    parser = argparse.ArgumentParser('commcare-hq-export', 'Output a customized export of CommCareHQ data.')

    #parser.add_argument('--query-format', choices=['json', 'xls', 'xlsx'], default='json') # possibly eventually concrete syntax
    parser.add_argument('--query', help='JSON string or file name. If omitted, reads from standard input (--username must be provided)')
    parser.add_argument('--commcare-hq', default='prod')
    parser.add_argument('--api-version', default=LATEST_KNOWN_VERSION)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--output-format', default='json', choices=['json', 'csv', 'xls', 'xlsx'], help='Output format')
    parser.add_argument('--output', metavar='PATH', default='reports.zip', help='Path to output; defaults to `reports.zip`.')

    args = parser.parse_args(argv)

    if args.query:
        if os.path.exists(args.query):
            with open(args.query) as fh:
                args.query = fh.read()
        # else it should already be a legit JSON string
    else:
        args.query = sys.stdin.read()

    #if args.query_format == 'json':
    query = MiniLinq.from_jvalue(json.loads(args.query))
    #elif args.query_format == 'xlsx':
    #    import openpyxl
    #    workbook = openpyxl.load_workbook(args.query)
    #    query = excel_query.compile(workbook)
    #else:
    #    raise NotImplementedError()

    if not args.username:
        args.username = raw_input('Pleaes provide a username: ')

    if not args.password:
        args.password = getpass.getpass('Please enter your password: ')

    # Build an API client using either the URL provided, or the URL for a known alias
    api_client = CommCareHqClient(url = commcare_hq_aliases.get(args.commcare_hq, args.commcare_hq), 
                                  domain = args.domain,
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
    # SQLite?
    
    env = BuiltInEnv() | CommCareHqEnv(api_client) | JsonPathEnv({}) # {'form': api_client.iterate('form')})
    results = query.eval(env)

    # Assume that if any tables were emitted, that is the idea, otherwise print the output
    if len(list(env.emitted_tables())) > 0:
        with writer:
            for table in env.emitted_tables():
                writer.write_table(table)

        if args.output_format == 'json':
            print json.dumps(writer.tables, indent=4, default=RepeatableIterator.to_jvalue)
    else:
        print json.dumps(list(results), indent=4, default=RepeatableIterator.to_jvalue)

def entry_point():
    main(sys.argv[1:])
    
if __name__ == '__main__':
    entry_point()
