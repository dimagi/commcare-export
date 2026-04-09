Python Library Usage
====================

As a library, the various `commcare_export` modules make it easy to:

- Interact with the CommCare HQ REST API
- Execute [MiniLinq](minilinq-reference.md) queries against the API
- Load and save JSON representations of MiniLinq queries
- Compile Excel configurations to MiniLinq queries


CommCare HQ API Client
----------------------

To directly access the CommCare HQ REST API:

```python
from commcare_export.checkpoint import CheckpointManagerWithDetails
from commcare_export.commcare_hq_client import CommCareHqClient, AUTH_MODE_APIKEY
from commcare_export.commcare_minilinq import get_paginator, PaginationMode

username = 'some@username.com'
domain = 'your-awesome-domain'
hq_host = 'https://www.commcarehq.org'
API_KEY= 'your_secret_api_key'

api_client = CommCareHqClient(hq_host, domain, username, API_KEY, AUTH_MODE_APIKEY)
case_paginator=get_paginator(resource='case', pagination_mode=PaginationMode.date_modified)
case_paginator.init()
checkpoint_manager=CheckpointManagerWithDetails(None, None, PaginationMode.date_modified)

cases = api_client.iterate('case', case_paginator, checkpoint_manager=checkpoint_manager)

for case in cases:
	print(case['case_id'])

```

The `CommCareHqClient` supports two authentication modes:

- `AUTH_MODE_PASSWORD` - Username and password authentication
- `AUTH_MODE_APIKEY` - API key authentication (recommended)


Executing MiniLinq Queries
--------------------------

To issue a MiniLinq query against the API, and print the query as JSON:

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

### Environment Composition

MiniLinq query evaluation relies on composing multiple environments:

- `BuiltInEnv()` - Built-in functions (math, string operations, etc.)
- `CommCareHqEnv(api_client)` - The `api_data` function for fetching
  from CommCare HQ
- `JsonPathEnv()` - JSON path navigation (e.g., `form.gender`)

These are composed using the `|` operator:

```python
env = BuiltInEnv() | CommCareHqEnv(api_client) | JsonPathEnv()
```


See Also
--------

- [MiniLinq Reference](minilinq-reference.md)
- [Query Formats](query-formats.md)
- [Output Formats](output-formats.md)
