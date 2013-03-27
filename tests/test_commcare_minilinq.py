import unittest
import simplejson
import urllib
from itertools import *

from commcare_export.minilinq import *
from commcare_export.env import *
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.commcare_minilinq import *

class TestCommCareMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def check_case(self, val, result):
        if isinstance(val, list):
            assert [datum.value for datum in val] == list(result)

    def test_eval(self):
        def die(msg): raise Exception(msg)
        
        client = MockCommCareHqClient({
            'form': [
                (
                    {'limit': 100, '_search': simplejson.dumps({"filter":"test1"}, separators=(',',':'))},
                    [1, 2, 3],
                ),
                (
                    {'limit': 100, '_search': simplejson.dumps({"filter":"test2"}, separators=(',', ':'))},
                    [
                        { 'x': [{ 'y': 1 }, {'y': 2}] },
                        { 'x': [{ 'y': 3 }, {'z': 4}] },
                        { 'x': [{ 'y': 5 }] }
                    ]
                ),
                (
                    {'limit': 100, '_search': simplejson.dumps({'filter':'laziness-test'}, separators=(',', ':'))},
                    (i if i < 5 else die('Not lazy enough') for i in range(12))
                )
            ]
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

        self.check_case(FlatMap(source=Apply(Reference('api_data'),
                                             Literal('form'),
                                             Literal({"filter": 'test2'})),
                                body=Reference('x[*].y')).eval(env),
                        [1, 2, 3, 5])

        self.check_case(islice(Apply(Reference('api_data'),
                                 Literal('form'),
                                 Literal({"filter": "laziness-test"})).eval(env), 5),
                        [0, 1, 2, 3, 4])
