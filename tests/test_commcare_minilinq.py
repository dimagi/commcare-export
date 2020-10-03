import unittest
from itertools import *

from jsonpath_rw import jsonpath

from commcare_export.checkpoint import CheckpointManagerWithSince
from commcare_export.minilinq import *
from commcare_export.env import *
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.commcare_minilinq import *

class TestCommCareMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def check_case(self, val, result):
        if isinstance(result, list):
            assert [datum.value if isinstance(datum, jsonpath.DatumInContext) else datum for datum in val] == result

    def test_eval(self):
        def die(msg): raise Exception(msg)

        client = MockCommCareHqClient({
            'form': [
                (
                    {'limit': 1000, 'filter': 'test1', 'order_by': 'indexed_on'},
                    [1, 2, 3],
                ),
                (
                    {'limit': 1000, 'filter': 'test2', 'order_by': 'indexed_on'},
                    [
                        { 'x': [{ 'y': 1 }, {'y': 2}] },
                        { 'x': [{ 'y': 3 }, {'z': 4}] },
                        { 'x': [{ 'y': 5 }] }
                    ]
                ),
                (
                    {'limit': 1000, 'filter': 'laziness-test', 'order_by': 'indexed_on'},
                    (i if i < 5 else die('Not lazy enough') for i in range(12))
                ),
                (
                    {'limit': 1000, 'cases__full': 'true', 'order_by': 'indexed_on'},
                    [1, 2, 3, 4, 5]
                ),
            ],

            'case': [
                (
                    {'limit': 1000, 'type': 'foo', 'order_by': 'indexed_on'},
                    [
                        { 'x': 1 },
                        { 'x': 2 },
                        { 'x': 3 },
                    ]
                )
            ],

            'user': [
                (
                    {'limit': 1000},
                    [
                        { 'x': 1 },
                        { 'x': 2 },
                        { 'x': 3 },
                    ]
                )
            ]
        })

        env = BuiltInEnv() | CommCareHqEnv(client) | JsonPathEnv({}) # {'form': api_client.iterate('form')})

        checkpoint_manager = CheckpointManagerWithSince(None, None)
        assert list(Apply(Reference('api_data'),
                          Literal('form'),
                          Literal(checkpoint_manager),
                          Literal({"filter": 'test1'})).eval(env)) == [1, 2, 3]

        # just check that we can still apply some deeper xpath by mapping; first ensure the basics work
        assert list(Apply(Reference('api_data'),
                          Literal('form'),
                          Literal(checkpoint_manager),
                          Literal({"filter": 'test2'})).eval(env)) == [
                    { 'x': [{ 'y': 1 }, {'y': 2}] },
                    { 'x': [{ 'y': 3 }, {'z': 4}] },
                    { 'x': [{ 'y': 5 }] }
                ]

        self.check_case(FlatMap(source=Apply(Reference('api_data'),
                                             Literal('form'),
                                             Literal(checkpoint_manager),
                                             Literal({"filter": 'test2'})),
                                body=Reference('x[*].y')).eval(env),
                        [1, 2, 3, 5])

        self.check_case(islice(Apply(Reference('api_data'),
                                     Literal('form'),
                                     Literal(checkpoint_manager),
                                     Literal({"filter": "laziness-test"})).eval(env), 5),
                        [0, 1, 2, 3, 4])

        self.check_case(Apply(Reference('api_data'),
                              Literal('form'),
                              Literal(checkpoint_manager),
                              Literal(None),
                              Literal(['cases'])).eval(env),
                        [1, 2, 3, 4, 5])

        self.check_case(FlatMap(source=Apply(Reference('api_data'),
                                             Literal('case'),
                                             Literal(checkpoint_manager),
                                             Literal({'type': 'foo'})),
                                body=Reference('x')).eval(env),
                        [1, 2, 3])

        self.check_case(FlatMap(source=Apply(Reference('api_data'),
                                             Literal('user'),
                                             Literal(checkpoint_manager),
                                             Literal(None)),
                                body=Reference('x')).eval(env),
                        [1, 2, 3])
