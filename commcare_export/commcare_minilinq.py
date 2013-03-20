"""
CommCare/Export-specific extensions to MiniLinq. 

To date, this is simply built-ins for querying the
API directly.
"""

import simplejson
from commcare_export.env import DictEnv, CannotBind, CannotReplace


class CommCareHqEnv(DictEnv):
    """
    An environment providing primitives for pulling from the
    CommCareHq API.
    """
    
    def __init__(self, commcare_hq_client, since=None):
        self.commcare_hq_client = commcare_hq_client
        self.since = since
        super(CommCareHqEnv, self).__init__({
            'api_data' : self.api_data
        })

    def api_data(self, resource, payload=None):
        payload = dict(payload or {}) # Do not mutate passed-in dicts

        if self.since:
            if resource == 'form':
                key = 'received_on'
            elif resource == 'case':
                key = 'server_modified_date'
            else:
                raise ValueError('Cannot use `since` with resource %s' % resource)
            
            if 'filter' not in payload: payload['filter'] = {}
            payload['filter'] = {
                "and": [
                    payload.get("filter", {"match_all":{}}),
                    {'range': {key: {'from': self.since.isoformat()}}},
                ]
            }

        params = {'limit': 100}

        if payload:
            params.update({'_search': simplejson.dumps(payload, separators=(',',':'))}) # compact encoding
        
        return self.commcare_hq_client.iterate(resource, params=params)

    def bind(self, name, value):
        raise CannotBind()

    def replace(self, data):
        raise CannotReplace()
