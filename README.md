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
>>> api_client = CommCareHqClient('http://commcarehq.org', domain='your_domain').authenticated('your_username', getpass.getpass())
>>> saved_query = Map(source=Apply(Reference("api_data"), [Literal("form"), Literal({"filter": {"term": {"app_id": "whatever"}}})])
                      body=List([Reference("received_on"), Reference("form.gender")]))

>>> forms = saved_query.eval(BuiltInEnv() | CommCareHqEnv(api_client) | JsonPathEnv())
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

MiniLinq Reference
------------------

The abstract syntax can be directly inspected in the `commcare_export.minilinq` module. Note that the choice between functions and primitives is deliberately chosen
to expose the structure of the MiniLinq for possible optimization, and to restrict the overall language.

Here is a description of the astract syntax and semantics

| Python                      | JSON                                                | What is evaluates to
|-----------------------------|-----------------------------------------------------|---------------------------------
| `Literal(v)`                | `{"Lit": v}`                                        | Just `v`
| `Reference(x)`              | `{"Ref": x}`                                        | Whatever `x` resolves to in the environment
| `List([a, b, c, ...])`      | `{"List": [a, b, c, ...}`                           | The list of what `a`, `b`, `c` evaluate to
| `Map(source, name, body)`   | `{"Map": {"source": ..., "name": ..., "body": ...}` | Evals `body` for each elem in `source`. If `name` is provided, the elem will be bound to it, otherwise it will replace the whole env.
| `FlatMap(source, name, body)` | `{"FlatMap": {"source" ... etc}}` | Flattens after mapping, like nested list comprehensions
| `Filter(source, name, body)`  | etc |
| `Bind(value, name, body)`     | etc | Binds the result of `value` to `name` when evaluating `body`
| `Emit(table, headings, rows)` | etc | Emits `table` with `headings` and `rows`. Note that `table` is a string, `headings` is a list of expressions, and `rows` is a list of lists of expressions. See explanation belowe for emitted output.
| `Apply(fn, args)` | etc | Evaluates `fn` to a function, and all of `args`, then applies the function to the args.

Built in functions like `api_data` and basic arithmetic and comparison are provided via the environment,
referred to be name using `Ref`, and utilized via `Apply`

Output Formats
--------------

Your MiniLinq may define multiple tables with headings in addition to their body rows by using `Emit`
expressions, or may simply return the results of a single query.

If your MiniLinq does not contain any `Emit` expressions, then the results of the expression will be
printed to standard output as pretty-printed JSON.

If your MiniLinq _does_ contain `Emit` expressions, then there are many formats available, selected
via the `--output-format <format>` option, and it can be directed to a file with the `--output <file>` command-line option.

 - `json`: The tables will each be a member of a JSON dictionary, printed to standard outputv
 - `csv`: Each table will be a CSV file within a Zip archive.
 - `xls`: Each table will be a sheet in an old-format Excel spreadsheet.
 - `xlsx`: Each table will be a sheet in a new-format Excel spreadsheet.

