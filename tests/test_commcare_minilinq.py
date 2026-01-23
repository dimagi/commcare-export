from itertools import islice

from jsonpath_ng import jsonpath

from commcare_export.checkpoint import CheckpointManagerWithDetails
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.commcare_minilinq import (
    CommCareHqEnv,
    PaginationMode,
    get_paginator,
)
from commcare_export.env import BuiltInEnv, JsonPathEnv
from commcare_export.minilinq import Apply, FlatMap, Literal, Reference


class TestCommCareMiniLinq:

    def test_eval_indexed_on(self):
        _run_eval(PaginationMode.date_indexed)

    def test_eval_modified_on(self):
        _run_eval(PaginationMode.date_modified)


def _check_case(val, result):
    if isinstance(result, list):
        assert [
            datum.value
            if isinstance(datum, jsonpath.DatumInContext) else datum
            for datum in val
        ] == result


def _run_eval(pagination_mode):
    form_order_by = get_paginator(
        'form', pagination_mode=pagination_mode
    ).since_field
    case_order_by = get_paginator(
        'case', pagination_mode=pagination_mode
    ).since_field

    def die(msg):
        raise Exception(msg)

    client = MockCommCareHqClient({
        'form': [
            (
                {
                    'limit': 1000,
                    'filter': 'test1',
                    'order_by': form_order_by
                },
                [1, 2, 3],
            ),
            ({
                'limit': 1000,
                'filter': 'test2',
                'order_by': form_order_by
            }, [{
                'x': [{
                    'y': 1
                }, {
                    'y': 2
                }]
            }, {
                'x': [{
                    'y': 3
                }, {
                    'z': 4
                }]
            }, {
                'x': [{
                    'y': 5
                }]
            }]),
            ({
                'limit': 1000,
                'filter': 'laziness-test',
                'order_by': form_order_by
            },
             (i if i < 5 else die('Not lazy enough') for i in range(12))),
            ({
                'limit': 1000,
                'cases__full': 'true',
                'order_by': form_order_by
            }, [1, 2, 3, 4, 5]),
        ],
        'case': [({
            'limit': 1000,
            'type': 'foo',
            'order_by': case_order_by
        }, [
            {
                'x': 1
            },
            {
                'x': 2
            },
            {
                'x': 3
            },
        ])],
        'user': [({
            'limit': 1000
        }, [
            {
                'x': 1
            },
            {
                'x': 2
            },
            {
                'x': 3
            },
        ])]
    })

    env = BuiltInEnv() | CommCareHqEnv(client) | JsonPathEnv({})

    checkpoint_manager = CheckpointManagerWithDetails(
        None, None, pagination_mode
    )
    assert list(
        Apply(
            Reference('api_data'), Literal('form'),
            Literal(checkpoint_manager), Literal({"filter": 'test1'})
        ).eval(env)
    ) == [1, 2, 3]

    assert list(
        Apply(
            Reference('api_data'), Literal('form'),
            Literal(checkpoint_manager), Literal({"filter": 'test2'})
        ).eval(env)
    ) == [{
        'x': [{
            'y': 1
        }, {
            'y': 2
        }]
    }, {
        'x': [{
            'y': 3
        }, {
            'z': 4
        }]
    }, {
        'x': [{
            'y': 5
        }]
    }]

    _check_case(
        FlatMap(
            source=Apply(
                Reference('api_data'), Literal('form'),
                Literal(checkpoint_manager), Literal({"filter": 'test2'})
            ),
            body=Reference('x[*].y')
        ).eval(env), [1, 2, 3, 5]
    )

    _check_case(
        islice(
            Apply(
                Reference('api_data'), Literal('form'),
                Literal(checkpoint_manager),
                Literal({"filter": "laziness-test"})
            ).eval(env), 5
        ), [0, 1, 2, 3, 4]
    )

    _check_case(
        Apply(
            Reference('api_data'), Literal('form'),
            Literal(checkpoint_manager), Literal(None), Literal(['cases'])
        ).eval(env), [1, 2, 3, 4, 5]
    )

    _check_case(
        FlatMap(
            source=Apply(
                Reference('api_data'), Literal('case'),
                Literal(checkpoint_manager), Literal({'type': 'foo'})
            ),
            body=Reference('x')
        ).eval(env), [1, 2, 3]
    )

    _check_case(
        FlatMap(
            source=Apply(
                Reference('api_data'), Literal('user'),
                Literal(checkpoint_manager), Literal(None)
            ),
            body=Reference('x')
        ).eval(env), [1, 2, 3]
    )
