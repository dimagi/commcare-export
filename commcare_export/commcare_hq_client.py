from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import logging
from collections import OrderedDict
from copy import deepcopy

import requests
from datetime import datetime
from requests.auth import HTTPDigestAuth

AUTH_MODE_SESSION = 'session'
AUTH_MODE_DIGEST = 'digest'

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

    def __init__(self, url, project, version=LATEST_KNOWN_VERSION, session=None, auth=None):
        self.version = version
        self.url = url
        self.project = project
        self.__session = session
        self.__auth = auth
        self._checkpoint_manager = None
        self._checkpoint_kwargs = {}

    @property
    def session(self):
        if self.__session == None:
            self.__session = requests.Session(headers={'User-Agent': 'commcare-export/%s' % commcare_export.__version__})
        return self.__session

    @property
    def api_url(self):
        return '%s/a/%s/api/v%s' % (self.url, self.project, self.version)

    def authenticated(self, username=None, password=None, mode=AUTH_MODE_SESSION):
        """
        Returns a freshly authenticated CommCareHqClient with a new session.
        This is safe to call many times and each of the resulting clients
        remain independent, so you can log in with zero, one, or many users.
        """
        session = requests.Session()
        auth = None
        if mode == AUTH_MODE_SESSION:
            login_url = '%s/accounts/login/' % self.url

            # Pick up things like CSRF cookies and form fields by doing a GET first
            response = session.get(login_url)
            if response.status_code != 200:
                raise Exception('Failed to connect to authentication page (%s): %s' % (response.status_code, response.text))

            response = session.post(login_url,
                                    headers = {'Referer': login_url },
                                    data = {'username': username,
                                            'password': password,
                                            'csrfmiddlewaretoken': response.cookies['csrftoken']})

            if response.status_code != 200:
                raise Exception('Authentication failed (%s): %s' % (response.status_code, response.text))
            
        elif mode == 'digest':
            auth = HTTPDigestAuth(username, password)
        else:
            raise Exception('Unknown auth mode: %s' % mode)

        return CommCareHqClient(url=self.url, project=self.project, version=self.version, session=session, auth=auth)

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
                fetch_start = datetime.utcnow()
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

                self.checkpoint(fetch_start)
                
        return RepeatableIterator(iterate_resource)

    def set_checkpoint_manager(self, manager, **checkpoint_kwargs):
        self._checkpoint_manager = manager
        self._checkpoint_kwargs = checkpoint_kwargs

    def checkpoint(self, checkpoint_time):
        if self._checkpoint_manager:
            kwargs = deepcopy(self._checkpoint_kwargs)
            kwargs.update({
                'checkpoint_time': checkpoint_time
            })
            with self._checkpoint_manager:
                self._checkpoint_manager.set_checkpoint(**kwargs)

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

    def authenticated(self, *args, **kwargs):
        return self

    def get(self, resource, paginator, params=None):
        return self.mock_data[resource][urlencode(OrderedDict(sorted(d.items())))]
    
    def iterate(self, resource, paginator, params=None):
        return self.mock_data[resource][urlencode(OrderedDict(sorted(params.items())))]

