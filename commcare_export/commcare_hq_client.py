from __future__ import (
    absolute_import,
    division,
    generators,
    nested_scopes,
    print_function,
    unicode_literals,
)

import copy
import logging
from collections import OrderedDict
from urllib.parse import urlencode

import requests
from requests.auth import AuthBase, HTTPDigestAuth

import backoff
import commcare_export
from commcare_export.repeatable_iterator import RepeatableIterator

AUTH_MODE_PASSWORD = 'password'
AUTH_MODE_APIKEY = 'apikey'

logger = logging.getLogger(__name__)

LATEST_KNOWN_VERSION = '0.5'
RESOURCE_REPEAT_LIMIT = 10


def on_backoff(details):
    _log_backoff(details, 'Waiting for retry.')


def on_giveup(details):
    _log_backoff(details, 'Giving up.')


def _log_backoff(details, action_message):
    details['__suffix'] = action_message
    logger.warning(
        "Request failed after {tries} attempts ({elapsed:.1f}s). {__suffix}"
        .format(**details)
    )


def is_client_error(ex):
    logger.info(str(ex))
    if hasattr(ex, 'response') and ex.response is not None:
        if ex.response.status_code == 429:
            # "Too Many Requests": HQ wants us to back off
            return False
        return 400 <= ex.response.status_code < 500
    return False


class ResourceRepeatException(Exception):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class CommCareHqClient(object):
    """
    A connection to CommCareHQ for a particular version, project, and user.
    """

    def __init__(
        self,
        url,
        project,
        username,
        password,
        auth_mode=AUTH_MODE_PASSWORD,
        version=LATEST_KNOWN_VERSION,
        checkpoint_manager=None
    ):
        self.version = version
        self.url = url
        self.project = project
        self.__auth = self._get_auth(username, password, auth_mode)
        self.__session = None

    def _get_auth(self, username, password, mode):
        if mode == AUTH_MODE_PASSWORD:
            return HTTPDigestAuth(username, password)
        elif mode == AUTH_MODE_APIKEY:
            return ApiKeyAuth(username, password)
        else:
            raise Exception('Unknown auth mode: %s' % mode)

    @property
    def session(self):
        if self.__session == None:
            self.__session = requests.Session()
            self.__session.headers.update({
                'User-Agent': f'commcare-export/{commcare_export.__version__}'
            })
        return self.__session

    @session.setter
    def session(self, session):
        """Used for overriding the session in unit tests"""
        self.__session = session

    @property
    def api_url(self):
        return '%s/a/%s/api/v%s' % (self.url, self.project, self.version)

    @backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        max_time=300,
        giveup=is_client_error,
        on_backoff=on_backoff,
        on_giveup=on_giveup
    )
    def get(self, resource, params=None):
        """
        Gets the named resource.

        Currently a bit of a vulnerable stub that works for this
        particular use case in the hands of a trusted user; would likely
        want this to work like (or via) slumber.
        """
        logger.debug("Fetching '%s' batch: %s", resource, params)
        resource_url = '{self.api_url}/{resource}/'
        response = self.session.get(
            resource_url, params=params, auth=self.__auth, timeout=60
        )
        response.raise_for_status()
        return response.json()

    def iterate(
        self,
        resource,
        paginator,
        params=None,
        checkpoint_manager=None,
    ):
        """
        Assumes the endpoint is a list endpoint, and iterates over it
        making a lot of assumptions that it is like a tastypie endpoint.
        """
        UNKNOWN_COUNT = 'unknown'
        params = dict(params or {})

        def iterate_resource(resource=resource, params=params):
            more_to_fetch = True
            last_batch_ids = set()
            total_count = UNKNOWN_COUNT
            fetched = 0
            repeat_counter = 0
            last_params = None

            while more_to_fetch:
                if params == last_params:
                    repeat_counter += 1
                else:
                    repeat_counter = 0
                if repeat_counter >= RESOURCE_REPEAT_LIMIT:
                    raise ResourceRepeatException(
                        f"Requested resource '{resource}' {repeat_counter} "
                        "times with same parameters"
                    )

                batch = self.get(resource, params)
                last_params = copy.copy(params)
                batch_meta = batch['meta']
                if total_count == UNKNOWN_COUNT or fetched >= total_count:
                    if batch_meta.get('total_count'):
                        total_count = int(batch_meta['total_count'])
                    else:
                        total_count = UNKNOWN_COUNT
                    fetched = 0

                batch_objects = batch['objects']
                fetched += len(batch_objects)
                logger.debug('Received %s of %s', fetched, total_count)
                if not batch_objects:
                    more_to_fetch = False
                else:
                    got_new_data = False
                    for obj in batch_objects:
                        if obj['id'] not in last_batch_ids:
                            yield obj
                            got_new_data = True

                    if batch_meta.get('next'):
                        last_batch_ids = {obj['id'] for obj in batch_objects}
                        params = paginator.next_page_params_from_batch(batch)
                        if not params:
                            more_to_fetch = False
                    else:
                        more_to_fetch = False

                    limit = batch_meta.get('limit')
                    if more_to_fetch:
                        # Handle the case where API is 'non-counting'
                        # and repeats the last batch
                        repeated_last_page_of_non_counting_resource = (
                            not got_new_data and total_count == UNKNOWN_COUNT
                            and (limit and len(batch_objects) < limit)
                        )
                        more_to_fetch = not repeated_last_page_of_non_counting_resource

                    self.checkpoint(
                        checkpoint_manager, paginator, batch, not more_to_fetch
                    )

        return RepeatableIterator(iterate_resource)

    def checkpoint(self, checkpoint_manager, paginator, batch, is_final):
        from commcare_export.commcare_minilinq import DatePaginator
        if isinstance(paginator, DatePaginator):
            since_date = paginator.get_since_date(batch)
            if since_date:
                try:
                    last_obj = batch['objects'][-1]
                except IndexError:
                    last_obj = {}
                checkpoint_manager.set_checkpoint(
                    since_date, is_final, doc_id=last_obj.get("id", None)
                )
            else:
                logger.warning(
                    'Failed to get a checkpoint date from a batch of data.'
                )


class MockCommCareHqClient(object):
    """
    An in-memory mock of the hq client, instantiated with a simple
    mapping of resource and params to results.

    Since dictionaries are not hashable, the mapping is written as a
    pair of tuples, handled appropriately internally.

    MockCommCareHqClient({
        'forms': [
            (
                {'_search': 'test1'},
                [
                   ... objects ...
                ]
            ),
        ]
    })
    """

    def __init__(self, mock_data):
        self.mock_data = {
            resource: {
                _params_to_url(params): result
                for params, result in resource_results
            } for resource, resource_results in mock_data.items()
        }

    def iterate(
        self, resource, paginator, params=None, checkpoint_manager=None
    ):
        logger.debug(
            'Mock client call to resource "%s" with params "%s"', resource,
            params
        )
        return self.mock_data[resource][_params_to_url(params)]

    def get(self, resource):
        logger.debug('Mock client call to get resource "%s"', resource)
        objects = self.mock_data[resource][_params_to_url({'get': True})]
        if objects:
            return {
                'meta': {
                    'limit': len(objects),
                    'next': None,
                    'offset': 0,
                    'previous': None,
                    'total_count': len(objects)
                },
                'objects': objects
            }
        else:
            return None


def _params_to_url(params):
    return urlencode(OrderedDict(sorted(params.items())))


class ApiKeyAuth(AuthBase):

    def __init__(self, username, apikey):
        self.username = username
        self.apikey = apikey

    def __eq__(self, other):
        return all([
            self.username == getattr(other, 'username', None),
            self.apikey == getattr(other, 'apikey', None)
        ])

    def __hash__(self):
        return hash((self.username, self.apikey))

    def __ne__(self, other):
        return not self == other

    def __call__(self, r):
        r.headers['Authorization'] = f'apikey {self.username}:{self.apikey}'
        return r
