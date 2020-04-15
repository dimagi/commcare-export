
TABLE_NAME = "commcare_locations"

# A JSON format MiniLinq query for internal CommCare location table.
# It reads every field produced by the /location/ API endpoint and
# writes the data to a table named "commcare_locations" in a database.
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
                        "Lit": "created_at"
                    },
                    {
                        "Lit": "domain"
                    },
                    {
                        "Lit": "external_id"
                    },
                    {
                        "Lit": "last_modified"
                    },
                    {
                        "Lit": "latitude"
                    },
                    {
                        "Lit": "location_data"
                    },
                    {
                        "Lit": "location_id"
                    },
                    {
                        "Lit": "location_type"
                    },
                    {
                        "Lit": "longitude"
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
                        "Lit": "site_code"
                    },
                    {
                        "Lit": "location_type_administrative"
                    },
                    {
                        "Lit": "location_type_code"
                    },
                    {
                        "Lit": "location_type_name"
                    },
                    {
                        "Lit": "location_type_parent"
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
                                    "Apply": {
                                        "fn": {
                                            "Ref": "str2date"
                                        },
                                        "args": [
                                            {
                                                "Ref": "created_at"
                                            }
                                        ]
                                    }
                                },
                                {
                                    "Ref": "domain"
                                },
                                {
                                    "Ref": "external_id"
                                },
                                {
                                    "Apply": {
                                        "fn": {
                                            "Ref": "str2date"
                                        },
                                        "args": [
                                            {
                                                "Ref": "last_modified"
                                            }
                                        ]
                                    }
                                },
                                {
                                    "Ref": "latitude"
                                },
                                {
                                    "Ref": "location_data"
                                },
                                {
                                    "Ref": "location_id"
                                },
                                {
                                    "Ref": "location_type"
                                },
                                {
                                    "Ref": "longitude"
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
                                    "Ref": "site_code"
                                },
                                {
                                    "Apply": {
                                        "fn": {
                                            "Ref": "get_location_info"
                                        },
                                        "args": [
                                            {
                                                "Ref": "location_type"
                                            },
                                            {
                                                "Lit": "administrative"
                                            }
                                        ]
                                    }
                                },
                                {
                                    "Apply": {
                                        "fn": {
                                            "Ref": "get_location_info"
                                        },
                                        "args": [
                                            {
                                                "Ref": "location_type"
                                            },
                                            {
                                                "Lit": "code"
                                            }
                                        ]
                                    }
                                },
                                {
                                    "Apply": {
                                        "fn": {
                                            "Ref": "get_location_info"
                                        },
                                        "args": [
                                            {
                                                "Ref": "location_type"
                                            },
                                            {
                                                "Lit": "name"
                                            }
                                        ]
                                    }
                                },
                                {
                                    "Apply": {
                                        "fn": {
                                            "Ref": "get_location_info"
                                        },
                                        "args": [
                                            {
                                                "Ref": "location_type"
                                            },
                                            {
                                                "Lit": "parent"
                                            }
                                        ]
                                    }
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
                                        "Lit": "location"
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
