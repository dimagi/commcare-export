import sys
import argparse
import json
import getpass
import requests
import pprint

from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.env import BuiltInEnv, JsonPathEnv
from commcare_export.minilinq import MiniLinq
from commcare_export.commcare_hq_client import CommCareHqClient
from commcare_export import writers
from commcare_export import excel_query

commcare_hq_aliases = {
    'local': 'http://localhost:8000',
    'prod': 'https://www.commcare-hq.org'
}

def main(argv):
    parser = argparse.ArgumentParser('commcare-hq-export', 'Output a customized export of CommCareHQ data.')

    parser.add_argument('--query-format', choices=['json', 'xls', 'xlsx'], default='json') # possibly eventually concrete syntax
    parser.add_argument('--query')
    parser.add_argument('--pure', default=False, action='store_true', help='Just output the results of the query, rather than the emitted tables')
    parser.add_argument('--commcare-hq', default='local') #default='https://commcare-hq.org') # Can be aliases or a URL
    parser.add_argument('--api-version', default='0.3')
    parser.add_argument('--domain', required=True)
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--output-format', default='json', choices=['json', 'csv', 'xls', 'xlsx'], help='Output format')
    parser.add_argument('--output', metavar='PATH', default='reports.zip', help='Path to output; defaults to `reports.zip`.')

    args = parser.parse_args(argv)

    if not args.username:
        args.username = raw_input('Pleaes provide a username: ')

    if not args.password:
        args.password = getpass.getpass('Please enter your password: ')

    # Build an API client using either the URL provided, or the URL for a known alias
    api_client = CommCareHqClient(url = commcare_hq_aliases.get(args.commcare_hq, args.commcare_hq), 
                                  domain = args.domain,
                                  version = args.api_version)

    api_client = api_client.authenticated(username=args.username, password=args.password)

    if not args.query:
        args.query = sys.stdin.read()

    if args.output_format == 'xlsx':
        writer = writers.Excel2007TableWriter(args.output)
    elif args.output_format == 'xls':
        writer = writers.Excel2003TableWriter(args.output)
    elif args.output_format == 'csv':
        writer = writers.CsvTableWriter(args.output)
    elif args.output_format == 'json':
        writer = writers.JValueTableWriter()
    # SQLite?
    
    if args.query_format == 'json':
        query = MiniLinq.from_jvalue(json.loads(args.query))
    elif args.query_format == 'xlsx':
        import openpyxl
        workbook = openpyxl.load_workbook(args.query)
        query = excel_query.compile(workbook)
    else:
        raise NotImplementedError()
        
    env = BuiltInEnv() | JsonPathEnv({'form': api_client.iterate('form')})
    results = query.eval(env)

    if args.pure:
        print json.dumps(list(results), indent=4, default=RepeatableIterator.to_jvalue)
    else:
        with writer:
            for table in env.emitted_tables():
                writer.write_table(table)

        if args.output_format == 'json':
            print json.dumps(writer.tables, indent=4, default=RepeatableIterator.to_jvalue)

def entry_point():
    main(sys.argv[1:])
    
if __name__ == '__main__':
    entry_point()
