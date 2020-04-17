from commcare_export.misc import unwrap_val

# LocationInfoProvider uses the /location_type/ endpoint of the API
# to retrieve location type data, stores that information in a dictionary
# keyed by resource URI and provides the method 'get_location_info' to
# extract values from the dictionary.

class LocationInfoProvider:
    def __init__(self, api_client):
        self._api_client = api_client
        self._location_types = None

    @property
    def location_types(self):
        if self._location_types is None:
            self._location_types = get_location_types(self._api_client)
        return self._location_types

    def get_location_info(self, resource_uri, field):
        unwrapped_uri = unwrap_val(resource_uri)
        location_type = self.location_types[unwrapped_uri]
        if location_type is None:
            return None
        else:
            return location_type[field]

def get_location_types(api_client):
    response = api_client.get('location_type')
    location_type_dict = {}
    for row in response['objects']:
        location_type_dict[row['resource_uri']] = row
    return location_type_dict


