import logging

from commcare_export.misc import unwrap_val
from commcare_export.commcare_minilinq import SimplePaginator

logger = logging.getLogger(__name__)

# LocationInfoProvider uses the /location_type/ endpoint of the API
# to retrieve location type data, stores that information in a dictionary
# keyed by resource URI and provides the method 'get_location_info' to
# extract values from the dictionary.

class LocationInfoProvider:
    def __init__(self, api_client, page_size):
        self._api_client = api_client
        self._page_size = page_size
        self._location_types = None
        self._location_hierarchy = None

    @property
    def location_types(self):
        if self._location_types is None:
            self._location_types = self.get_location_types()
        return self._location_types

    def get_location_info(self, resource_uri, field):
        unwrapped_uri = unwrap_val(resource_uri)
        if unwrapped_uri in self.location_types:
            location_type = self.location_types[unwrapped_uri]
            if field in self.location_types[unwrapped_uri]:
                return location_type[field]
        return None

    def get_location_ancestor(self, resource_uri, location_type_code):
        unwrapped_uri = unwrap_val(resource_uri)
        if unwrapped_uri in self.location_hierarchy:
            location_hierarchy = self.location_hierarchy[unwrapped_uri]
            if location_type_code in location_hierarchy:
                return location_hierarchy[location_type_code]
        return None

    def get_location_types(self):
        paginator = SimplePaginator('location_type', self._page_size)
        paginator.init(None, False, None)
        location_type_dict = {}
        for row in self._api_client.iterate('location_type', paginator,
                                              {'limit': self._page_size}):
            location_type_dict[row['resource_uri']] = row
        return location_type_dict

    @property
    def location_hierarchy(self):
        if self._location_hierarchy is None:
            self._location_hierarchy = self.get_location_hierarchy()
        return self._location_hierarchy

    def get_location_hierarchy(self):
        paginator = SimplePaginator('location', self._page_size)
        paginator.init(None, False, None)

        # Extract every location, its type and its parent
        location_data = {}
        for row in self._api_client.iterate('location', paginator,
                                            {'limit': self._page_size}):
            location_data[row['resource_uri']] = {
                'location_id': row['location_id'],
                'location_type': row['location_type'],
                'parent': row['parent'] if 'parent' in row else None
            }

        # Build a map from location resource_uri to a map from
        # location_type_code to ancestor location id.
        ancestors = {}        # includes location itself
        for resource_uri in location_data:
            loc_uri = resource_uri
            type_code_to_id = {}
            while loc_uri is not None:
                if loc_uri not in location_data:
                    logger.warning('Unknown location referenced: {}'.format(loc_uri))
                    break

                loc_data = location_data[loc_uri]
                loc_type = loc_data['location_type']
                if loc_type not in self.location_types:
                    logger.warning('Unknown location type referenced: {}'.format(loc_type))
                    break

                type_code = self.location_types[loc_type]['code']
                type_code_to_id[type_code] = loc_data['location_id']
                loc_uri = loc_data['parent']
            ancestors[resource_uri] = type_code_to_id
        return ancestors


