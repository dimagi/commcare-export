import unittest
import simplejson
import urllib

from commcare_export.minilinq import *
from commcare_export.env import *
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.commcare_minilinq import *

class TestCommCareMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_eval(self):
        client = MockCommCareHqClient({
            'form': {
                urllib.urlencode({'_search': simplejson.dumps({"filter":"test1"})}): [1, 2, 3],
                urllib.urlencode({'_search': simplejson.dumps({"filter":"test2"})}): [
                    { 'x': [{ 'y': 1 }, {'y': 2}] },
                    { 'x': [{ 'y': 3 }, {'z': 4}] },
                    { 'x': [{ 'y': 5 }] }
                ],
            }
        })

        env = BuiltInEnv() | CommCareHqEnv(client) | JsonPathEnv({}) # {'form': api_client.iterate('form')})

        assert list(Apply(Reference('api_data'),
                          Literal('form'),
                          Literal({"filter": 'test1'})).eval(env)) == [1, 2, 3]

        # just check that we can still apply some deeper xpath by mapping; first ensure the basics work
        assert list(Apply(Reference('api_data'),
                                     Literal('form'),
                                     Literal({"filter": 'test2'})).eval(env)) == [
                    { 'x': [{ 'y': 1 }, {'y': 2}] },
                    { 'x': [{ 'y': 3 }, {'z': 4}] },
                    { 'x': [{ 'y': 5 }] }
                ]

        assert list(FlatMap(source=Apply(Reference('api_data'),
                                     Literal('form'),
                                     Literal({"filter": 'test2'})),
                        body=Reference('x[*].y')).eval(env)) == [1, 2, 3, 5]
