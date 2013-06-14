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

    def api_data(self, resource, payload=None, include_referenced_items=None):
        payload = dict(payload or {}) # Do not mutate passed-in dicts
        params = {'limit': 100}

        # Currently the form resource endpoint and the case resource endpoint are completely different
        if resource == 'form':
            if self.since:
                if 'filter' not in payload: payload['filter'] = {}

                payload['filter'] = {
                    "and": [
                        payload.get("filter", {"match_all":{}}),
                        {'range': {'received_on': {'from': self.since.isoformat()}}},
                    ]
                }

            if payload:
                params.update({'_search': simplejson.dumps(payload, separators=(',',':'))}) # compact encoding
                
        elif resource == 'case':
            if self.since:
                payload['server_date_modified_start'] = self.since.isoformat()

            if payload:
                params.update(payload)

        else:
            raise ValueError('I do not know how to access the API resource "%s"' % resource)

        if include_referenced_items:
            params.update([ ('%s__full' % referenced_item, 'true') for referenced_item in include_referenced_items])
        
        return self.commcare_hq_client.iterate(resource, params=params)

    def bind(self, name, value):
        raise CannotBind()

    def replace(self, data):
        raise CannotReplace()
