from commcare_export.misc import unwrap_val

# This module is designed to read location type information from CommCare HQ
# and keep it in memory to be combined with location information. The pieces
# work as follows:
# 1. Execute the MiniLinq query stored in 'jvalue' with a JValueTableWriter.
# 2. Call 'build_dictionary' on the result to create a more easily accessed
#    dictionary of location type information.
# 3. Bind a LocationInfoProvider containing the dictionary in the environment
#    when executing the location query.

TABLE_NAME = "commcare_location_types"

# A JSON format MiniLinq query for internal CommCare location type table.
# It reads every field produced by the /location_type/ API endpoint and
# writes the data to an internal table to be joined with location table data.
jvalue = {
    "Bind": {
        "name": "checkpoint_manager",
        "value": {
            "Apply": {
                "fn": {
                    "Ref": "get_checkpoint_manager"
                },
                "args": [
                    {
                        "Lit": [
                            TABLE_NAME
                        ]
                    }
                ]
            }
        },
        "body": {
            "Emit": {
                "table": TABLE_NAME,
                "headings": [
                    {
                        "Lit": "id"
                    },
                    {
                        "Lit": "administrative"
                    },
                    {
                        "Lit": "code"
                    },
                    {
                        "Lit": "domain"
                    },
                    {
                        "Lit": "name"
                    },
                    {
                        "Lit": "parent"
                    },
                    {
                        "Lit": "resource_uri"
                    },
                    {
                        "Lit": "shares_cases"
                    },
                    {
                        "Lit": "view_descendants"
                    }
                ],
                "source": {
                    "Map": {
                        "body": {
                            "List": [
                                {
                                    "Ref": "id"
                                },
                                {
                                    "Ref": "administrative"
                                },
                                {
                                    "Ref": "code"
                                },
                                {
                                    "Ref": "domain"
                                },
                                {
                                    "Ref": "name"
                                },
                                {
                                    "Ref": "parent"
                                },
                                {
                                    "Ref": "resource_uri"
                                },
                                {
                                    "Ref": "shares_cases"
                                },
                                {
                                    "Ref": "view_descendants"
                                }
                            ]
                        },
                        "source": {
                            "Apply": {
                                "fn": {
                                    "Ref": "api_data"
                                },
                                "args": [
                                    {
                                        "Lit": "location_type"
                                    },
                                    {
                                        "Ref": "checkpoint_manager"
                                    }
                                ]
                            }
                        },
                        "name": None
                    }
                },
                "missing_value": None
            }
        }
    }
}


def build_dictionary(location_types):
    # Convert to a dictionary of dictionaries, keyed by location type
    # resource URI
    location_type_dict = {}
    headings = location_types[TABLE_NAME]['headings']
    rows = location_types[TABLE_NAME]['rows']
    for row in rows:
        resource_uri = None
        row_dict = {}
        assert len(row) == len(headings)
        for i in range(0, len(headings)):
            row_dict[headings[i]] = row[i]
            if headings[i] == 'resource_uri':
                resource_uri = row[i]

        if resource_uri is not None:
            location_type_dict[resource_uri] = row_dict

    return location_type_dict


class LocationInfoProvider:
    def __init__(self, location_types):
        self.location_types = location_types

    def get_location_info(self, resource_uri, field):
        unwrapped_uri = unwrap_val(resource_uri)
        location_type = self.location_types[unwrapped_uri]
        if location_type is None:
            return None
        else:
            return location_type[field]
