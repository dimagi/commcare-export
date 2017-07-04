"""
CommCare/Export-specific extensions to MiniLinq.

To date, this is simply built-ins for querying the
API directly.
"""

from commcare_export.env import DictEnv, CannotBind, CannotReplace
from datetime import datetime

try:
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs


resource_since_params = {
    'form': ('received_on_start', 'received_on_end'),
    'case': ('server_date_modified_start', 'server_date_modified_end'),
    'device-log': ('date__gte', 'date__lte'),
    'user': None,
    'application': None,
    'web-user': None,
}

def get_paginator(resource):
    return {
        'form': DatePaginator('form', 'received_on'),
        'case': DatePaginator('case', 'server_date_modified'),
        'device-log': SimplePaginator('device-log'),
        'user': SimplePaginator('user'),
        'application': SimplePaginator('application'),
        'web-user': SimplePaginator('web-user'),
    }[resource]


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
        if resource not in resource_since_params:
            raise ValueError('I do not know how to access the API resource "%s"' % resource)

        paginator = get_paginator(resource)
        paginator.init(payload, include_referenced_items, self.until)
        initial_params = paginator.next_page_params_since(self.since)
        return self.commcare_hq_client.iterate(resource, paginator, params=initial_params)

    def bind(self, name, value):
        raise CannotBind()

    def replace(self, data):
        raise CannotReplace()


class SimplePaginator(object):
    """
    Paginate based on the 'next' URL provided in the API response.
    """
    def __init__(self, resource):
        self.resource = resource

    def init(self, payload=None, include_referenced_items=None, until=None):
        self.payload = dict(payload or {})  # Do not mutate passed-in dicts
        self.include_referenced_items = include_referenced_items
        self.until = until

    def next_page_params_since(self, since=None):
        params = self.payload
        params['limit'] = 1000

        resource_date_params = resource_since_params[self.resource]
        if (since or self.until) and resource_date_params:
            since_param, until_param = resource_date_params
            if since:
                params[since_param] = since.isoformat()

            if self.until:
                params[until_param] = self.until.isoformat()

        if self.include_referenced_items:
            params.update([('%s__full' % referenced_item, 'true') for referenced_item in self.include_referenced_items])

        return params

    def next_page_params_from_batch(self, batch):
        if batch['meta']['next']:
            return parse_qs(urlparse(batch['meta']['next']).query)


class DatePaginator(SimplePaginator):
    """
    This paginator is designed to get around the issue of deep paging where the deeper the page the longer
    the query takes.

    Paginate records according to a date in the record. The params for the next batch will include a filter
    for the date of the last record in the previous batch.

    This also adds an ordering parameter to ensure that the records are ordered by the date field in ascending order.

    :param resource: The name of the resource being fetched: ``form`` or ``case``.
    :param since_field: The name of the date field to use for pagination.
    """
    def __init__(self, resource, since_field):
        super(DatePaginator, self).__init__(resource)
        self.since_field = since_field

    def next_page_params_since(self, since=None):
        params = super(DatePaginator, self).next_page_params_since(since)
        params['order_by'] = self.since_field
        return params

    def next_page_params_from_batch(self, batch):
        try:
            last_obj = batch['objects'][-1]
        except IndexError:
            return

        since = last_obj and last_obj.get(self.since_field)
        if since:
            since_date = None
            for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S.%fZ'):
                try:
                    since_date = datetime.strptime(since, fmt)
                except ValueError:
                    pass
            if since_date:
                return self.next_page_params_since(since_date)
