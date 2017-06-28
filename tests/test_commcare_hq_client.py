from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import unittest

import simplejson

import requests

from commcare_export.commcare_hq_client import CommCareHqClient
from commcare_export.commcare_minilinq import SimplePaginator, DatePaginator, resource_since_params


class FakeSession(object):
    def get(self, resource_url, params=None, auth=None):
        result = self._get_results(params)
        # Mutatey construction method required by requests.Response
        response = requests.Response()
        response._content = simplejson.dumps(result).encode('utf-8')
        response.status_code = 200
        return response

    def _get_results(self, params):
        if params:
            assert params['offset'][0] == '1'
            return {
                'meta': { 'next': None, 'offset': params['offset'][0], 'limit': 1, 'total_count': 2 },
                'objects': [ {'id': 1, 'foo': 2} ]
            }
        else:
            return {
                'meta': { 'next': '?offset=1', 'offset': 0, 'limit': 1, 'total_count': 2 },
                'objects': [ {'id': 2, 'foo': 1} ]
            }


class FakeDateSession(FakeSession):
    def __init__(self, resource):
        self.since_query_param = resource_since_params[resource][0]

    def _get_results(self, params):
        if not params:
            return {
                'meta': {'next': '?offset=1', 'offset': 0, 'limit': 1, 'total_count': 2},
                'objects': [{'id': 1, 'foo': 1, 'since_field': '2017-01-01T15:36:22Z'}]
            }
        else:
            assert params[self.since_query_param] == '2017-01-01T15:36:22'
            # include ID=1 again to make sure it gets filtered out
            return {
                'meta': { 'next': None, 'offset': 1, 'limit': 1, 'total_count': 2 },
                'objects': [ {'id': 1, 'foo': 1}, {'id': 2, 'foo': 2} ]
            }


class TestCommCareHqClient(unittest.TestCase):

    def _test_iterate(self, session, paginator):
        client = CommCareHqClient('/fake/commcare-hq/url', project='fake-project', session=session)

        # Iteration should do two "gets" because the first will have something in the "next" metadata field
        paginator.init()
        results = list(client.iterate('/fake/uri', paginator))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['foo'], 1)
        self.assertEqual(results[1]['foo'], 2)

    def test_iterate_simple(self):
        self._test_iterate(FakeSession(), SimplePaginator('fake'))

    def test_iterate_date(self):
        self._test_iterate(FakeDateSession('form'), DatePaginator('form', 'since_field'))
        self._test_iterate(FakeDateSession('case'), DatePaginator('case', 'since_field'))
