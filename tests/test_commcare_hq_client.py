from datetime import datetime
from unittest.mock import patch

import requests
import simplejson
from requests.structures import CaseInsensitiveDict

import pytest
from commcare_export.checkpoint import CheckpointManagerWithDetails
from commcare_export.commcare_hq_client import (
    CommCareHqClient,
    ResourceRepeatException,
)
from commcare_export.commcare_minilinq import (
    DATE_PARAMS,
    DatePaginator,
    PaginationMode,
    SimplePaginator,
    get_paginator,
)


class FakeSession:

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
                'meta': {
                    'next': None,
                    'offset': params['offset'][0],
                    'limit': 1,
                    'total_count': 2
                },
                'objects': [{
                    'id': 1,
                    'foo': 2
                }]
            }
        else:
            return {
                'meta': {
                    'next': '?offset=1',
                    'offset': 0,
                    'limit': 1,
                    'total_count': 2
                },
                'objects': [{
                    'id': 2,
                    'foo': 1
                }]
            }


class FakeDateCaseSession(FakeSession):

    def _get_results(self, params):
        if not params:
            return {
                'meta': {
                    'next': '?offset=1',
                    'offset': 0,
                    'limit': 1,
                    'total_count': 2
                },
                'objects': [{
                    'id': 1,
                    'foo': 1,
                    'indexed_on': '2017-01-01T15:36:22Z'
                }]
            }
        else:
            since_query_param = DATE_PARAMS['indexed_on'].start_param
            assert params[since_query_param] == '2017-01-01T15:36:22'
            # include ID=1 again to make sure it gets filtered out
            return {
                'meta': {
                    'next': None,
                    'offset': 1,
                    'limit': 1,
                    'total_count': 2
                },
                'objects': [{
                    'id': 1,
                    'foo': 1
                }, {
                    'id': 2,
                    'foo': 2
                }]
            }


class FakeRepeatedDateCaseSession(FakeSession):
    # Model the case where there are as many or more cases with the same
    # indexed_on than the batch size (2), so the client requests the
    # same set of cases in a loop.
    def _get_results(self, params):
        if not params:
            return {
                'meta': {
                    'next': '?offset=1',
                    'offset': 0,
                    'limit': 2,
                    'total_count': 4
                },
                'objects': [{
                    'id': 1,
                    'foo': 1,
                    'indexed_on': '2017-01-01T15:36:22Z'
                }, {
                    'id': 2,
                    'foo': 2,
                    'indexed_on': '2017-01-01T15:36:22Z'
                }]
            }
        else:
            since_query_param = DATE_PARAMS['indexed_on'].start_param
            assert params[since_query_param] == '2017-01-01T15:36:22'
            return {
                'meta': {
                    'next': '?offset=1',
                    'offset': 0,
                    'limit': 2,
                    'total_count': 4
                },
                'objects': [{
                    'id': 1,
                    'foo': 1,
                    'indexed_on': '2017-01-01T15:36:22Z'
                }, {
                    'id': 2,
                    'foo': 2,
                    'indexed_on': '2017-01-01T15:36:22Z'
                }]
            }


class FakeMessageLogSession(FakeSession):

    def _get_results(self, params):
        obj_1 = {
            'id': 1,
            'foo': 1,
            'date_last_activity': '2017-01-01T15:36:22Z'
        }
        obj_2 = {
            'id': 2,
            'foo': 2,
            'date_last_activity': '2017-01-01T15:37:22Z'
        }
        obj_3 = {
            'id': 3,
            'foo': 3,
            'date_last_activity': '2017-01-01T15:38:22Z'
        }
        if not params:
            return {
                'meta': {
                    'next': '?cursor=xyz',
                    'limit': 2
                },
                'objects': [obj_1, obj_2]
            }
        else:
            since_query_param = DATE_PARAMS['date_last_activity'].start_param
            since = params[since_query_param]
            if since == '2017-01-01T15:37:22':
                return {
                    'meta': {
                        'next': '?cursor=xyz',
                        'limit': 2
                    },
                    'objects': [obj_3]
                }
            if since == '2017-01-01T15:38:22':
                return {'meta': {'next': None, 'limit': 2}, 'objects': []}

            raise Exception(since)


class FakeDateFormSession(FakeSession):

    def _get_results(self, params):
        since1 = '2017-01-01T15:36:22'
        since2 = '2017-01-01T16:00:00'
        if not params:
            return {
                'meta': {
                    'next': '?offset=1',
                    'offset': 0,
                    'limit': 1,
                    'total_count': 3
                },
                'objects': [{
                    'id': 1,
                    'foo': 1,
                    'indexed_on': f'{since1}Z'
                }]
            }
        else:
            since_query_param = DATE_PARAMS['indexed_on'].start_param
            indexed_on = params[since_query_param]
            if indexed_on == since1:
                # include ID=1 again to make sure it gets filtered out
                return {
                    'meta': {
                        'next': '?offset=2',
                        'offset': 0,
                        'limit': 1,
                        'total_count': 3
                    },
                    'objects': [{
                        'id': 1,
                        'foo': 1
                    }, {
                        'id': 2,
                        'foo': 2,
                        'indexed_on': f'{since2}Z'
                    }]
                }
            elif indexed_on == since2:
                return {
                    'meta': {
                        'next': None,
                        'offset': 0,
                        'limit': 1,
                        'total_count': 3
                    },
                    'objects': [{
                        'id': 3,
                        'foo': 3
                    }]
                }
            else:
                raise Exception(indexed_on)


def _iterate_with_paginator(session, paginator, expected_count, expected_vals):
    client = CommCareHqClient(
        '/fake/commcare-hq/url', 'fake-project', None, None
    )
    client.session = session

    paginator.init()
    checkpoint_manager = CheckpointManagerWithDetails(
        None, None, PaginationMode.date_indexed
    )
    results = list(
        client.iterate(
            '/fake/uri', paginator, checkpoint_manager=checkpoint_manager
        )
    )
    assert len(results) == expected_count
    assert [result['foo'] for result in results] == expected_vals


class TestCommCareHqClient:

    def test_iterate_simple(self):
        _iterate_with_paginator(
            FakeSession(), SimplePaginator('fake'), 2, [1, 2]
        )

    def test_iterate_date(self):
        _iterate_with_paginator(
            FakeDateFormSession(), get_paginator('form'), 3, [1, 2, 3]
        )
        _iterate_with_paginator(
            FakeDateCaseSession(), get_paginator('case'), 2, [1, 2]
        )

    def test_repeat_limit(self):
        with pytest.raises(
            ResourceRepeatException,
            match="Requested resource '/fake/uri' 10 times with same parameters"
        ):
            _iterate_with_paginator(
                FakeRepeatedDateCaseSession(), get_paginator('case', 2), 2,
                [1, 2]
            )

    def test_message_log(self):
        _iterate_with_paginator(
            FakeMessageLogSession(), get_paginator('messaging-event', 2), 3,
            [1, 2, 3]
        )

    @pytest.mark.parametrize(
        "headers,expected",
        [
            ({'Retry-After': "0.0"}, False),
            ({}, True),
        ],
    )
    def test_should_raise_for_status(self, headers, expected):
        response = requests.Response()
        response.headers = CaseInsensitiveDict(headers)
        client = CommCareHqClient(
            '/fake/commcare-hq/url', 'fake-project', None, None
        )

        assert client._should_raise_for_status(response) is expected

    @patch('commcare_export.commcare_hq_client.logger')
    @patch("commcare_export.commcare_hq_client.CommCareHqClient.session")
    def test_get_with_forbidden_response_in_non_debug_mode(self, session_mock, logger_mock):
        response = requests.Response()
        response.status_code = 401
        session_mock.get.return_value = response

        logger_mock.isEnabledFor.return_value = False

        with pytest.raises(SystemExit):
            CommCareHqClient(
                '/fake/commcare-hq/url', 'fake-project', None, None
            ).get("location")

        logger_mock.error.assert_called_once_with(
            "#401 Client Error: None for url: None. "
            "Please ensure that your CommCare HQ credentials are correct and auth-mode is passed as 'apikey' "
            "if using API Key to authenticate. Also, verify that your account has access to the project "
            "and the necessary permissions to use commcare-export.")

    @patch('commcare_export.commcare_hq_client.logger')
    @patch("commcare_export.commcare_hq_client.CommCareHqClient.session")
    def test_get_with_other_http_failure_response_in_non_debug_mode(self, session_mock, logger_mock):
        response = requests.Response()
        response.status_code = 404
        session_mock.get.return_value = response

        logger_mock.isEnabledFor.return_value = False

        with pytest.raises(SystemExit):
            CommCareHqClient(
                '/fake/commcare-hq/url', 'fake-project', None, None
            ).get("location")

        logger_mock.error.assert_called_once_with(
            "404 Client Error: None for url: None")

    @patch('commcare_export.commcare_hq_client.logger')
    @patch("commcare_export.commcare_hq_client.CommCareHqClient.session")
    def test_get_with_http_failure_response_in_debug_mode(self, session_mock, logger_mock):
        response = requests.Response()
        response.status_code = 404
        session_mock.get.return_value = response

        logger_mock.isEnabledFor.return_value = True

        with pytest.raises(
            Exception, match="404 Client Error: None for url: None"
        ):
            CommCareHqClient(
                '/fake/commcare-hq/url', 'fake-project', None, None
            ).get("location")


class TestDatePaginator:
    def test_empty_batch(self):
        assert (
            DatePaginator('since', params=SimplePaginator()
                         ).next_page_params_from_batch({'objects': []})
        ) is None

    def test_bad_date(self):
        assert (
            DatePaginator('since', params=SimplePaginator()
                         ).next_page_params_from_batch({
                             'objects': [{
                                 'since': 'not a date'
                             }]
                         })
        ) is None

    def test_multi_field_sort(self):
        d1 = '2017-01-01T15:36:22Z'
        d2 = '2017-01-01T18:36:22Z'
        paginator = DatePaginator(['s1', 's2'], params=SimplePaginator())
        assert paginator.get_since_date({'objects': [{
            's1': d1,
            's2': d2
        }]}) == datetime.strptime(d1, '%Y-%m-%dT%H:%M:%SZ')

        assert paginator.get_since_date({'objects': [{
            's2': d2
        }]}) == datetime.strptime(d2, '%Y-%m-%dT%H:%M:%SZ')

        assert paginator.get_since_date({'objects': [{
            's1': None,
            's2': d2
        }]}) == datetime.strptime(d2, '%Y-%m-%dT%H:%M:%SZ')
