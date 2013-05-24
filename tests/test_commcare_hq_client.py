from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import unittest
import simplejson
from itertools import *

import requests

from commcare_export.commcare_hq_client import CommCareHqClient

class FakeSession(object):
    def get(self, resource_url, params=None):
        if params:
            result = {
                'meta': { 'next': None, 'offset': params['offset'][0], 'limit': 1, 'total_count': 2 },
                'objects': [ {'foo': 2} ]
            }
        else:
            result = {
                'meta': { 'next': '?offset=1', 'offset': 0, 'limit': 1, 'total_count': 2 },
                'objects': [ {'foo': 1} ]
            }

        # Mutatey construction method required by requests.Response
        response = requests.Response()
        response._content = simplejson.dumps(result).encode('utf-8')
        response.status_code = 200
        return response

class TestCommCareHqClient(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_iterate(self):
        client = CommCareHqClient('/fake/commcare-hq/url', project='fake-project', session = FakeSession())

        # Iteration should do two "gets" because the first will have something in the "next" metadata field
        results = list(client.iterate('/fake/uri'))
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['foo'], 1)
        self.assertEqual(results[1]['foo'], 2)
