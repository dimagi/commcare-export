from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import json
import unittest
from datetime import datetime

import simplejson

import requests

from commcare_export.checkpoint import CheckpointManagerWithSince
from commcare_export.commcare_hq_client import CommCareHqClient
from commcare_export.commcare_minilinq import SimplePaginator, DatePaginator, resource_since_params, get_paginator


class FakeSession(object):
    def get(self, resource_url, params=None, auth=None, timeout=None):
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
                'objects': [{'id': 1, 'foo': 1, 'indexed_on': '2017-01-01T15:36:22Z'}]
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
        since1 = '2017-01-01T15:36:22'
        since2 = '2017-01-01T16:00:00'
        if not params:
            return {
                'meta': {'next': '?offset=1', 'offset': 0, 'limit': 1, 'total_count': 3},
                'objects': [{'id': 1, 'foo': 1, 'indexed_on': '{}Z'.format(since1)}]
            }
        else:
            since_query_param = resource_since_params['form'].start_param
            indexed_on = params[since_query_param]
            if indexed_on == since1:
                # include ID=1 again to make sure it gets filtered out
                return {
                    'meta': { 'next': '?offset=2', 'offset': 0, 'limit': 1, 'total_count': 3 },
                    'objects': [{'id': 1, 'foo': 1}, {'id': 2, 'foo': 2, 'indexed_on': '{}Z'.format(since2)}]
                }
            elif indexed_on == since2:
                return {
                    'meta': { 'next': None, 'offset': 0, 'limit': 1, 'total_count': 3 },
                    'objects': [{'id': 3, 'foo': 3}]
                }
            else:
                raise Exception(indexed_on)


class TestCommCareHqClient(unittest.TestCase):

    def _test_iterate(self, session, paginator, expected_count, expected_vals):
        client = CommCareHqClient('/fake/commcare-hq/url', 'fake-project', None, None)
        client.session = session

        # Iteration should do two "gets" because the first will have something in the "next" metadata field
        paginator.init()
        checkpoint_manager = CheckpointManagerWithSince(None, None)
        results = list(client.iterate('/fake/uri', paginator, checkpoint_manager=checkpoint_manager))
        self.assertEqual(len(results), expected_count)
        self.assertEqual([result['foo'] for result in results], expected_vals)

    def test_iterate_simple(self):
        self._test_iterate(FakeSession(), SimplePaginator('fake'), 2, [1, 2])

    def test_iterate_date(self):
        self._test_iterate(FakeDateFormSession(), get_paginator('form'), 3, [1, 2, 3])
        self._test_iterate(FakeDateCaseSession(), get_paginator('case'), 2, [1, 2])


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

    def test_multi_field_sort(self):
        d1 = '2017-01-01T15:36:22Z'
        d2 = '2017-01-01T18:36:22Z'
        self.assertEqual(DatePaginator('fake', ['s1', 's2']).get_since_date({'objects': [{
            's1': d1,
            's2': d2
        }]}), datetime.strptime(d1, '%Y-%m-%dT%H:%M:%SZ'))

        self.assertEqual(DatePaginator('fake', ['s1', 's2']).get_since_date({'objects': [{
            's2': d2
        }]}), datetime.strptime(d2, '%Y-%m-%dT%H:%M:%SZ'))

        self.assertEqual(DatePaginator('fake', ['s1', 's2']).get_since_date({'objects': [{
            's1': None,
            's2': d2
        }]}), datetime.strptime(d2, '%Y-%m-%dT%H:%M:%SZ'))

