"""
CommCare/Export-specific extensions to MiniLinq.

To date, this is simply built-ins for querying the
API directly.
"""
import json
from enum import Enum

from commcare_export.env import CannotBind, CannotReplace, DictEnv
from commcare_export.misc import unwrap
from dateutil.parser import ParserError, parse

try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse


SUPPORTED_RESOURCES = {
    'form', 'case', 'user', 'location', 'application', 'web-user', 'messaging-event'
}


class PaginationMode(Enum):
    date_indexed = "date_indexed"
    date_modified = "date_modified"


class SimpleSinceParams(object):
    def __init__(self, start, end):
        self.start_param = start
        self.end_param = end

    def __call__(self, since, until):
        params = {}
        if since:
            params[self.start_param] = since.isoformat()
        if until:
            params[self.end_param] = until.isoformat()
        return params


class FormFilterSinceParams(object):
    def __call__(self, since, until):
        range_expression = {}
        if since:
            range_expression['gte'] = since.isoformat()

        if until:
            range_expression['lte'] = until.isoformat()

        server_modified_missing = {"missing": {
            "field": "server_modified_on", "null_value": True, "existence": True}
        }
        query = json.dumps({
            'filter': {
                "or": [
                    {
                        "and": [
                            {
                                "not": server_modified_missing
                            },
                            {
                                "range": {
                                    "server_modified_on": range_expression
                                }
                            }
                        ]
                    },
                    {
                        "and": [
                            server_modified_missing,
                            {
                                "range": {
                                    "received_on": range_expression
                                }
                            }
                        ]
                    }
                ]
            }})

        return {'_search': query}


DATE_PARAMS = {
    'indexed_on': SimpleSinceParams('indexed_on_start', 'indexed_on_end'),
    'server_date_modified': SimpleSinceParams('server_date_modified_start', 'server_date_modified_end'),
    'date': SimpleSinceParams('date__gte', 'date__lt'),  # used by messaging-events
}


def get_paginator(resource, page_size=1000, pagination_mode=PaginationMode.date_indexed):
    return {
        PaginationMode.date_indexed: {
            'form': DatePaginator('indexed_on', page_size),
            'case': DatePaginator('indexed_on', page_size),
            'messaging-event': DatePaginator('date', page_size),
        },
        PaginationMode.date_modified: {
            'form': DatePaginator(['server_modified_on', 'received_on'], page_size, params=FormFilterSinceParams()),
            'case': DatePaginator('server_date_modified', page_size),
            'messaging-event': DatePaginator('date', page_size),
        }
    }[pagination_mode].get(resource, SimplePaginator(page_size))


class CommCareHqEnv(DictEnv):
    """
    An environment providing primitives for pulling from the
    CommCareHq API.
    """

    def __init__(self, commcare_hq_client, until=None, page_size=1000):
        self.commcare_hq_client = commcare_hq_client
        self.until = until
        self.page_size = page_size
        super(CommCareHqEnv, self).__init__({
            'api_data' : self.api_data
        })

    @unwrap('checkpoint_manager')
    def api_data(self, resource, checkpoint_manager, payload=None, include_referenced_items=None):
        if resource not in SUPPORTED_RESOURCES:
            raise ValueError('Unknown API resource "%s' % resource)

        paginator = get_paginator(resource, self.page_size, checkpoint_manager.pagination_mode)
        paginator.init(payload, include_referenced_items, self.until)
        initial_params = paginator.next_page_params_since(checkpoint_manager.since_param)
        return self.commcare_hq_client.iterate(
            resource, paginator,
            params=initial_params, checkpoint_manager=checkpoint_manager
        )

    def bind(self, name, value):
        raise CannotBind()

    def replace(self, data):
        raise CannotReplace()


class SimplePaginator(object):
    """
    Paginate based on the 'next' URL provided in the API response.
    """
    def __init__(self, page_size=1000, params=None):
        self.page_size = page_size
        self.params = params

    def init(self, payload=None, include_referenced_items=None, until=None):
        self.payload = dict(payload or {})  # Do not mutate passed-in dicts
        self.include_referenced_items = include_referenced_items
        self.until = until

    def next_page_params_since(self, since=None):
        params = self.payload
        params['limit'] = self.page_size

        if (since or self.until) and self.params:
            params.update(
                self.params(since, self.until)
            )

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

    :param since_field: The name of the date field to use for pagination.
    :param page_size: Number of results to request in each page
    """

    DEFAULT_PARAMS = object()

    def __init__(self, since_field, page_size=1000, params=DEFAULT_PARAMS):
        params = DATE_PARAMS[since_field] if params is DatePaginator.DEFAULT_PARAMS else params
        super(DatePaginator, self).__init__(page_size, params)
        self.since_field = since_field

    def next_page_params_since(self, since=None):
        params = super(DatePaginator, self).next_page_params_since(since)
        params['order_by'] = self.since_field
        return params

    def next_page_params_from_batch(self, batch):
        since_date = self.get_since_date(batch)
        if since_date:
            return self.next_page_params_since(since_date)

    def get_since_date(self, batch):
        try:
            last_obj = batch['objects'][-1]
        except IndexError:
            return

        if last_obj:
            if isinstance(self.since_field, list):
                for field in self.since_field:
                    since = last_obj.get(field)
                    if since:
                        break
            else:
                since = last_obj.get(self.since_field)

            if since:
                try:
                    return parse(since, ignoretz=True)  # ignoretz since we assume utc, and use naive datetimes everywhere
                except ParserError:
                    return None
