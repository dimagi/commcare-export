Python Library Usage
====================

*Part of [Technical Documentation](index.md)*

As a library, the various `commcare_export` modules make it easy to:

- Interact with the CommCare HQ REST API
- Execute "Minilinq" queries against the API (a very simple query
  language, described in the
  [MiniLinq Reference](minilinq-reference.md))
- Load and save JSON representations of Minilinq queries
- Compile Excel configurations to Minilinq queries


CommCare HQ API Client
----------------------

To directly access the CommCare HQ REST API:

```python
from commcare_export.checkpoint import CheckpointManagerWithDetails
from commcare_export.commcare_hq_client import CommCareHqClient, AUTH_MODE_APIKEY
from commcare_export.commcare_minilinq import get_paginator, PaginationMode

username = 'some@username.com'
domain = 'your-awesome-domain'
hq_host = 'https://commcarehq.org'
API_KEY= 'your_secret_api_key'

api_client = CommCareHqClient(hq_host, domain, username, API_KEY, AUTH_MODE_APIKEY)
case_paginator=get_paginator(resource='case', pagination_mode=PaginationMode.date_modified)
case_paginator.init()
checkpoint_manager=CheckpointManagerWithDetails(None, None, PaginationMode.date_modified)

cases = api_client.iterate('case', case_paginator, checkpoint_manager=checkpoint_manager)

for case in cases:
	print(case['case_id'])

```

### Authentication Modes

The `CommCareHqClient` supports two authentication modes:

- `AUTH_MODE_PASSWORD` - Username and password authentication
- `AUTH_MODE_APIKEY` - API key authentication (recommended)

### Pagination

The library provides different pagination strategies through the
`PaginationMode` enum:

- `PaginationMode.date_modified` - Paginate by date modified
  (recommended for cases)
- `PaginationMode.date_indexed` - Paginate by date indexed
- Other modes available in `commcare_minilinq.py`


Executing MiniLinq Queries
--------------------------

To issue a `minilinq` query against the API, and then print out that
query in a JSON serialization:

```python
import json
import sys
from commcare_export.minilinq import *
from commcare_export.commcare_hq_client import CommCareHqClient
from commcare_export.commcare_minilinq import CommCareHqEnv
from commcare_export.env import BuiltInEnv, JsonPathEnv
from commcare_export.writers import StreamingMarkdownTableWriter

api_client = CommCareHqClient(
    url="http://www.commcarehq.org",
    project='your_project',
    username='your_username',
    password='password',
    version='0.5'
)

source = Map(
   source=Apply(
       Reference("api_data"),
       Literal("form"),
       Literal({"filter": {"term": {"app_id": "whatever"}}})
   ),
   body=List([
       Reference("received_on"),
       Reference("form.gender"),
   ])
)

query = Emit(
   'demo-table',
   [
       Literal('Received On'),
       Literal('Gender')
   ],
   source
)

print(json.dumps(query.to_jvalue(), indent=2))

results = query.eval(BuiltInEnv() | CommCareHqEnv(api_client) | JsonPathEnv())

if len(list(env.emitted_tables())) > 0:
    with StreamingMarkdownTableWriter(sys.stdout) as writer:
        for table in env.emitted_tables():
            writer.write_table(table)
```

This will output JSON equivalent to this:

```json
{
    "Emit": {
        "headings": [
            {
                "Lit": "Received On"
            },
            {
                "Lit": "Gender"
            }
        ],
        "source": {
            "Map": {
                "body": {
                    "List": [
                        {
                            "Ref": "received_on"
                        },
                        {
                            "Ref": "form.gender"
                        }
                    ]
                },
                "name": null,
                "source": {
                    "Apply": {
                        "args": [
                            {
                                "Lit": "form"
                            },
                            {
                                "Lit": {
                                    "filter": {
                                        "term": {
                                            "app_id": "whatever"
                                        }
                                    }
                                }
                            }
                        ],
                        "fn": {
                            "Ref": "api_data"
                        }
                    }
                }
            }
        },
        "table": "demo-table"
    }
}
```


Environment Composition
-----------------------

The MiniLinq query evaluation relies on composing multiple environments:

- `BuiltInEnv()` - Provides built-in functions like math, string
  operations, etc.
- `CommCareHqEnv(api_client)` - Provides the `api_data` function for
  fetching from CommCare HQ
- `JsonPathEnv()` - Provides JSON path navigation (e.g., `form.gender`)

These are composed using the `|` operator:

```python
env = BuiltInEnv() | CommCareHqEnv(api_client) | JsonPathEnv()
results = query.eval(env)
```


Module Overview
---------------

The main modules in the `commcare_export` package:

- `commcare_hq_client` - REST API client for CommCare HQ
- `minilinq` - MiniLinq query language implementation
- `commcare_minilinq` - CommCare-specific MiniLinq extensions
- `env` - Execution environments for MiniLinq queries
- `excel_query` - Excel query parsing and compilation
- `writers` - Output format writers (CSV, Excel, SQL, JSON, Markdown)
- `checkpoint` - Checkpoint management for incremental exports
- `cli` - Command-line interface implementation


See Also
--------

- [MiniLinq Reference](minilinq-reference.md) - Complete language reference
- [Query Formats](query-formats.md) - Excel and JSON query specifications
- [Output Formats](output-formats.md) - Available output formats
