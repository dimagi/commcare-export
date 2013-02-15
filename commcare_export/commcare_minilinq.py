"""
CommCare/Export-specific extensions to MiniLinq. 

To date, this is simply built-ins for querying the
API directly.
"""

import simplejson
from commcare_export.env import DictEnv

class CommCareHqEnv(DictEnv):
    """
    An environment providing primitives for pulling from the
    CommCareHq API.
    """
    
    def __init__(self, commcare_hq_client):
        self.commcare_hq_client = commcare_hq_client
        return super(CommCareHqEnv, self).__init__({
            'api_data' : self.api_data
        })

    def api_data(self, resource, payload=None):
        params = {'_search': simplejson.dumps(payload)} if payload else None
        return self.commcare_hq_client.iterate(resource, params=params)

    def bind(self, name, value): raise CannotBind()
    def replace(self, data): raise CannotReplace()
