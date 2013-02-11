import sys
import argparse
import json
import getpass
import requests
import pprint

from commcare_export.jsonpath_env import JsonPathEnv
from commcare_export.minilinq import MiniLinq
from commcare_export.commcare_hq_client import CommCareHqClient

commcare_hq_aliases = {
    'local': 'http://localhost:8000',
    'prod': 'https://www.commcare-hq.org'
}

def main(argv):
    parser = argparse.ArgumentParser('commcare-hq-export', 'Output a customized export of CommCareHQ data.')

    parser.add_argument('--format', choices=['json', 'excel'], default='json') # possibly eventually concrete syntax
    parser.add_argument('--query')
    parser.add_argument('--commcare-hq', default='local') #default='https://commcare-hq.org') # Can be aliases or a URL
    parser.add_argument('--api-version', default='0.3')
    parser.add_argument('--domain', required=True)
    parser.add_argument('--username')
    parser.add_argument('--password')

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
    
    if args.format == 'json':
        records = [doc['_source'] for doc in api_client.get('xform_es')['hits']['hits']]
        env = JsonPathEnv({'xform_es': records})
        results = MiniLinq.from_jvalue(json.loads(args.query)).eval(env)
        pprint.pprint(list(results), indent=4)
    else:
        print 'Not yet!'

def entry_point():
    main(sys.argv[1:])
    
if __name__ == '__main__':
    entry_point()
