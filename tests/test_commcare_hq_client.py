from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import json
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


class FakeDateCaseSession(FakeSession):
    def _get_results(self, params):
        if not params:
            return {
                'meta': {'next': '?offset=1', 'offset': 0, 'limit': 1, 'total_count': 2},
                'objects': [{'id': 1, 'foo': 1, 'since_field': '2017-01-01T15:36:22Z'}]
            }
        else:
            since_query_param =resource_since_params['case'].start_param
            assert params[since_query_param] == '2017-01-01T15:36:22'
            # include ID=1 again to make sure it gets filtered out
            return {
                'meta': { 'next': None, 'offset': 1, 'limit': 1, 'total_count': 2 },
                'objects': [ {'id': 1, 'foo': 1}, {'id': 2, 'foo': 2} ]
            }

class FakeDateFormSession(FakeSession):
    def _get_results(self, params):
        if not params:
            return {
                'meta': {'next': '?offset=1', 'offset': 0, 'limit': 1, 'total_count': 2},
                'objects': [{'id': 1, 'foo': 1, 'since_field': '2017-01-01T15:36:22Z'}]
            }
        else:
            search = json.loads(params['_search'])
            _or = search['filter']['or']
            assert _or[0]['and'][1]['range']['server_modified_on']['gte'] == '2017-01-01T15:36:22'
            assert _or[1]['and'][1]['range']['received_on']['gte'] == '2017-01-01T15:36:22'
            # include ID=1 again to make sure it gets filtered out
            return {
                'meta': { 'next': None, 'offset': 1, 'limit': 1, 'total_count': 2 },
                'objects': [ {'id': 1, 'foo': 1}, {'id': 2, 'foo': 2} ]
            }


class TestCommCareHqClient(unittest.TestCase):

    def _test_iterate(self, session, paginator):
        client = CommCareHqClient('/fake/commcare-hq/url', 'fake-project', None, None)
        client.session = session

        # Iteration should do two "gets" because the first will have something in the "next" metadata field
        paginator.init()
        results = list(client.iterate('/fake/uri', paginator))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['foo'], 1)
        self.assertEqual(results[1]['foo'], 2)

    def test_iterate_simple(self):
        self._test_iterate(FakeSession(), SimplePaginator('fake'))

    def test_iterate_date(self):
        self._test_iterate(FakeDateFormSession(), DatePaginator('form', 'since_field'))
        self._test_iterate(FakeDateCaseSession(), DatePaginator('case', 'since_field'))


class TestDatePaginator(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_empty_batch(self):
        self.assertIsNone(DatePaginator('fake', 'since').next_page_params_from_batch({'objects': []}))

    def test_bad_date(self):
        self.assertIsNone(DatePaginator('fake', 'since').next_page_params_from_batch({'objects': [{
            'since': 'not a date'
        }]}))

