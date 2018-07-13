from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import logging
from collections import OrderedDict
from copy import deepcopy

import requests
from datetime import datetime
from requests.auth import HTTPDigestAuth
from requests.auth import AuthBase

AUTH_MODE_DIGEST = 'digest'
AUTH_MODE_APIKEY = 'apikey'

try:
    from urllib.request import urlopen
    from urllib.parse import urlparse, urlencode, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs
    from urllib import urlopen, urlencode

import commcare_export
from commcare_export.repeatable_iterator import RepeatableIterator

logger = logging.getLogger(__file__)

LATEST_KNOWN_VERSION='0.5'


class CommCareHqClient(object):
    """
    A connection to CommCareHQ for a particular version, project, and user.
    """

    def __init__(self, url, project, username, password,
                 auth_mode=AUTH_MODE_DIGEST, version=LATEST_KNOWN_VERSION, checkpoint_manager=None):
        self.version = version
        self.url = url
        self.project = project
        self._checkpoint_manager = checkpoint_manager
        self.__auth = self._get_auth(username, password, auth_mode)
        self.__session = None

    def _get_auth(self, username, password, mode):
        if mode == AUTH_MODE_DIGEST:
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
                'User-Agent': 'commcare-export/%s' % commcare_export.__version__
            })
        return self.__session

    @session.setter
    def session(self, session):
        """Used for overriding the session in unit tests"""
        self.__session = session

    @property
    def api_url(self):
        return '%s/a/%s/api/v%s' % (self.url, self.project, self.version)

    def get(self, resource, params=None):
        """
        Gets the named resource.

        Currently a bit of a vulnerable stub that works
        for this particular use case in the hands of a trusted user; would likely
        want this to work like (or via) slumber.
        """
        resource_url = '%s/%s/' % (self.api_url, resource)
        response = self.session.get(resource_url, params=params, auth=self.__auth)

        if response.status_code != 200:
            raise Exception('GET %s failed (%s): %s' % (resource_url, response.status_code, response.text))
        else:
            return response.json()
            
    def iterate(self, resource, paginator, params=None):
        """
        Assumes the endpoint is a list endpoint, and iterates over it
        making a lot of assumptions that it is like a tastypie endpoint.
        """
        params = dict(params or {})
        def iterate_resource(resource=resource, params=params):
            more_to_fetch = True
            last_batch_ids = set()

            while more_to_fetch:
                batch = self.get(resource, params)
                total_count = int(batch['meta']['total_count']) if batch['meta']['total_count'] else 'unknown'
                logger.debug('Received %s-%s of %s', 
                             batch['meta']['offset'], 
                             int(batch['meta']['offset'])+int(batch['meta']['limit']),
                             total_count)
                
                if not batch['objects']:
                    more_to_fetch = False
                else:
                    for obj in batch['objects']:
                        if obj['id'] not in last_batch_ids:
                            yield obj

                    if batch['meta']['next']:
                        last_batch_ids = {obj['id'] for obj in batch['objects']}
                        params = paginator.next_page_params_from_batch(batch)
                        if not params:
                            more_to_fetch = False
                    else:
                        more_to_fetch = False

                self.checkpoint(paginator, batch)
                
        return RepeatableIterator(iterate_resource)

    def checkpoint(self, paginator, batch):
        from commcare_export.commcare_minilinq import DatePaginator
        if self._checkpoint_manager and isinstance(paginator, DatePaginator):
            since_date = paginator.get_since_date(batch)
            with self._checkpoint_manager:
                self._checkpoint_manager.set_checkpoint(checkpoint_time=since_date)


class MockCommCareHqClient(object):
    """
    An in-memory mock of the hq client, instantiated
    with a simple mapping of resource and params to results.

    Since dictionaries are not hashable, the mapping is
    written as a pair of tuples, handled appropriately
    internallly.

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
        self.mock_data = dict([(resource, dict([(urlencode(OrderedDict(sorted(params.items()))), result) for params, result in resource_results]))
                              for resource, resource_results in mock_data.items()])

    def iterate(self, resource, paginator, params=None):
        logger.debug('Mock client call to resource "%s" with params "%s"', resource, params)
        return self.mock_data[resource][urlencode(OrderedDict(sorted(params.items())))]


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
        r.headers['Authorization'] = 'apikey %s:%s' % (self.username, self.apikey)
        return r

