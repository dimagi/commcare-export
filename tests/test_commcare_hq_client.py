from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import json
import unittest
from datetime import datetime

import simplejson

import requests

import pytest

from commcare_export.checkpoint import CheckpointManagerWithDetails
from commcare_export.commcare_hq_client import CommCareHqClient, ResourceRepeatException
from commcare_export.commcare_minilinq import SimplePaginator, DatePaginator, get_paginator, \
    DATE_PARAMS, PaginationMode


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
            since_query_param = DATE_PARAMS['indexed_on'].start_param
            assert params[since_query_param] == '2017-01-01T15:36:22'
            # include ID=1 again to make sure it gets filtered out
            return {
                'meta': { 'next': None, 'offset': 1, 'limit': 1, 'total_count': 2 },
                'objects': [ {'id': 1, 'foo': 1}, {'id': 2, 'foo': 2} ]
            }


class FakeRepeatedDateCaseSession(FakeSession):
    # Model the case where there are as many or more cases with the same
    # indexed_on than the batch size (2), so the client requests
    # the same set of cases in a loop.
    def _get_results(self, params):
        if not params:
            return {
                'meta': {'next': '?offset=1', 'offset': 0, 'limit': 2, 'total_count': 4},
                'objects': [{'id': 1, 'foo': 1, 'indexed_on': '2017-01-01T15:36:22Z'},
                            {'id': 2, 'foo': 2, 'indexed_on': '2017-01-01T15:36:22Z'}]
            }
        else:
            since_query_param = DATE_PARAMS['indexed_on'].start_param
            assert params[since_query_param] == '2017-01-01T15:36:22'
            return {
                'meta': { 'next': '?offset=1', 'offset': 0, 'limit': 2, 'total_count': 4},
                'objects': [{'id': 1, 'foo': 1, 'indexed_on': '2017-01-01T15:36:22Z'},
                            {'id': 2, 'foo': 2, 'indexed_on': '2017-01-01T15:36:22Z'}]
            }


class FakMessageLogSession(FakeSession):
    # for message logs, the last batch returns the same results in a loop, because
    # we use a non-counting paginator in tastypie that can't know if it's "finished"
    # We will gracefully treat this as success under the conditions where:
    #  - total_count is absent
    #  - the number of returned rows is fewer than the limit
    #  - the contents of the batch are the same
    def _get_results(self, params):
        obj_1 = {'id': 1, 'foo': 1, 'date': '2017-01-01T15:36:22Z'}
        obj_2 = {'id': 2, 'foo': 2, 'date': '2017-01-01T15:37:22Z'}
        if not params:
            return {
                'meta': {'next': '?offset=2', 'offset': 0, 'limit': 2, 'total_count': None},
                'objects': [obj_1, obj_2]
            }
        else:
            since_query_param = DATE_PARAMS['date'].start_param
            assert params[since_query_param] == '2017-01-01T15:37:22'
            return {
                'meta': { 'next': '?offset=1', 'offset': 0, 'limit': 2, 'total_count': None},
                'objects': [obj_2]
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
            since_query_param = DATE_PARAMS['indexed_on'].start_param
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
        checkpoint_manager = CheckpointManagerWithDetails(None, None, PaginationMode.date_indexed)
        results = list(client.iterate('/fake/uri', paginator, checkpoint_manager=checkpoint_manager))
        self.assertEqual(len(results), expected_count)
        self.assertEqual([result['foo'] for result in results], expected_vals)

    def test_iterate_simple(self):
        self._test_iterate(FakeSession(), SimplePaginator('fake'), 2, [1, 2])

    def test_iterate_date(self):
        self._test_iterate(FakeDateFormSession(), get_paginator('form'), 3, [1, 2, 3])
        self._test_iterate(FakeDateCaseSession(), get_paginator('case'), 2, [1, 2])

    def test_repeat_limit(self):
        with pytest.raises(ResourceRepeatException,
                           match="Requested resource '/fake/uri' 10 times with same parameters"):
            self._test_iterate(FakeRepeatedDateCaseSession(), get_paginator('case', 2), 2, [1, 2])

    def test_message_log(self):
        self._test_iterate(FakMessageLogSession(), get_paginator('messaging-event', 2), 2, [1, 2])


class TestDatePaginator(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_empty_batch(self):
        self.assertIsNone(DatePaginator('since', params=SimplePaginator()).next_page_params_from_batch({'objects': []}))

    def test_bad_date(self):
        self.assertIsNone(DatePaginator('since', params=SimplePaginator()).next_page_params_from_batch({'objects': [{
            'since': 'not a date'
        }]}))

    def test_multi_field_sort(self):
        d1 = '2017-01-01T15:36:22Z'
        d2 = '2017-01-01T18:36:22Z'
        paginator = DatePaginator(['s1', 's2'], params=SimplePaginator())
        self.assertEqual(paginator.get_since_date({'objects': [{
            's1': d1,
            's2': d2
        }]}), datetime.strptime(d1, '%Y-%m-%dT%H:%M:%SZ'))

        self.assertEqual(paginator.get_since_date({'objects': [{
            's2': d2
        }]}), datetime.strptime(d2, '%Y-%m-%dT%H:%M:%SZ'))

        self.assertEqual(paginator.get_since_date({'objects': [{
            's1': None,
            's2': d2
        }]}), datetime.strptime(d2, '%Y-%m-%dT%H:%M:%SZ'))

