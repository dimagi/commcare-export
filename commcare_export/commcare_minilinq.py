"""
CommCare/Export-specific extensions to MiniLinq. 

To date, this is simply built-ins for querying the
API directly.
"""

from commcare_export.env import DictEnv, CannotBind, CannotReplace

resource_since_params = {
    'form': ('received_on_start', 'received_on_end'),
    'case': ('server_date_modified_start', 'server_date_modified_end'),
    'device-log': ('date__gte', 'date__lte'),
    'user': None,
    'application': None,
    'web-user': None,
}

class CommCareHqEnv(DictEnv):
    """
    An environment providing primitives for pulling from the
    CommCareHq API.
    """
    
    def __init__(self, commcare_hq_client, since=None, until=None):
        self.commcare_hq_client = commcare_hq_client
        self.since = since
        self.until = until
        super(CommCareHqEnv, self).__init__({
            'api_data' : self.api_data
        })

    def api_data(self, resource, payload=None, include_referenced_items=None):
        payload = dict(payload or {}) # Do not mutate passed-in dicts
        params = {'limit': 1000}

        if resource not in resource_since_params:
            raise ValueError('I do not know how to access the API resource "%s"' % resource)

        if (self.since or self.until) and resource_since_params[resource]:
            since_param, until_param = resource_since_params[resource]
            if self.since:
                payload[since_param] = self.since.isoformat()

            if self.until:
                payload[until_param] = self.until.isoformat()

        if payload:
            params.update(payload)

        if include_referenced_items:
            params.update([ ('%s__full' % referenced_item, 'true') for referenced_item in include_referenced_items])
        
        return self.commcare_hq_client.iterate(resource, params=params)

    def bind(self, name, value):
        raise CannotBind()

    def replace(self, data):
        raise CannotReplace()
