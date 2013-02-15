CommCare Export
===============

A Python library and command-line tools to generate customized exports from CommCareHQ.


Installation
------------

```
$ pip install commcare-export
```


Usage
-----

In Python, the support code for this library makes it easy to directly access the CommCareHq REST API:

```python
>>> import getpass
>>> from commcare_export.commcare_hq_client import CommCareHqClient
>>> api_client = CommCareHqClient('http://commcarehq.org', domain='your_domain').authenticated('your_username', getpass.getpass())
>>> forms = api_client.iterate('form', {'app_id': "whatever"})
>>> [ (form['received_on'], form['form.gender']) for form in forms ]
```

You can also use the MiniLinq language, which is more machine-friendly than human-friendly, to
help support serialization/deserialization to JSON for building a tool to work with exports.

```python
>>> import getpass
>>> import json
>>> from commcare_export.minilinq import *
>>> from commcare_export.commcare_hq_client import CommCareHqClient
>>> from commcare_export.commcare_minilinq import CommCareHqEnv
>>> from commcare_export.env import BuiltInEnv
>>> api_client = CommCareHqClient('http://commcarehq.org', domain='your_domain').authenticated('your_username, getpass.getpass())
>>> saved_query = Map(source=Apply(Reference("api_data"), [Literal("form"), Literal({"filter": {"term": {"app_id": "whatever"}}})])
                      body=List([Reference("received_on"), Reference("form.gender")]))

>>> forms = saved_query.eval(BuiltInEnv() | CommCareHqEnv() | JsonPathEnv())
>>> print json.dumps(saved_query.to_jvalue(), indent=2)
```

Which will output JSON equivalent to this:

```javascript
{
  "Map": {
    "source": {
      "Apply": {
        "fn":   {"Ref": "api_data"},
        "args": [
          {"Lit": "form"},
          {"Lit": {"filter": {"term": {"app_id": "something"}}}}
        ],
      }
    },
    "body": {
      "List": [
        {"Ref": "received_on"},
        {"Ref": "form.gender"}
      ]
    }
  }
}
```

If you have saved the JSON representation of a query to a file, or are willing to type it in, then you can
also easily experiment on the command-line.

```
$ commcare-export --commcare-hq <URL or alias like "local" or "prod"> \
                  --username <username> \
                  --domain <domain> \
                  --version <api version, defaults to latest known> \
                  --query <file or raw json>
```

