
TABLE_NAME = "commcare_users"

# A JSON format MiniLinq query for internal CommCare user table.
# It reads every field produced by the /user/ API endpoint and
# writes the data to a table named "commcare_users" in a database.
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
                        "Lit": "default_phone_number"
                    },
                    {
                        "Lit": "email"
                    },
                    {
                        "Lit": "first_name"
                    },
                    {
                        "Lit": "groups"
                    },
                    {
                        "Lit": "last_name"
                    },
                    {
                        "Lit": "phone_numbers"
                    },
                    {
                        "Lit": "resource_uri"
                    },
                    {
                        "Lit": "commcare_location_id"
                    },
                    {
                        "Lit": "commcare_location_ids"
                    },
                    {
                        "Lit": "commcare_primary_case_sharing_id"
                    },
                    {
                        "Lit": "commcare_project"
                    },
                    {
                        "Lit": "username"
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
                                    "Ref": "default_phone_number"
                                },
                                {
                                    "Ref": "email"
                                },
                                {
                                    "Ref": "first_name"
                                },
                                {
                                    "Ref": "groups"
                                },
                                {
                                    "Ref": "last_name"
                                },
                                {
                                    "Ref": "phone_numbers"
                                },
                                {
                                    "Ref": "resource_uri"
                                },
                                {
                                    "Ref": "user_data.commcare_location_id"
                                },
                                {
                                    "Ref": "user_data.commcare_location_ids"
                                },
                                {
                                    "Ref":
                                    "user_data.commcare_primary_case_sharing_id"
                                },
                                {
                                    "Ref": "user_data.commcare_project"
                                },
                                {
                                    "Ref": "username"
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
                                        "Lit": "user"
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
