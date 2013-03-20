CommCare Export
===============

https://github.com/dimagi/commcare-export 

[![Build status](https://travis-ci.org/dimagi/commcare-export.png)](https://travis-ci.org/dimagi/commcare-export)

A Python library and command-line tool to generate customized exports from CommCareHQ.

Installation & Quick Start
--------------------------

```
$ pip install commcare-export
```

Or, during development:

```
$ git clone git@github.com:dimagi/commcare-export.git
$ cd commcare-export
$ mkvirtualenv commcare-export
$ pip install -e .
```

Now the fastest way to try it out is follow these steps:

1. Sign up for CommCare!
2. Create a project space.
3. Go to the CommCareHq Exchange and add the "Simple CommCare Demo/Tutorial" app to your project space.
4. Go to the app and enable CloudCare for the app and save it.
5. Go to the release manager, make a build, click the star to release it.
6. Go to cloudcare and in the registration module fill out a few registration forms.
7. Edit examples/demo-registrations.json to set the app_id to your app (it is in the URL bar when you are viewing the app)
8. Run this on the command line, with your info provided where indicated:

```
$ commcare-export \
     --query examples/demo-registration.json \
     --domain YOUR_DOMAIN \
     --output-format markdown
```


Command-line Usage
------------------

The basic usage of the command-line tool is with a saved Excel or JSON query (see how to write these, below)

```
$ commcare-export --commcare-hq <URL or alias like "local" or "prod"> \
                  --username <username> \
                  --domain <domain> \
                  --version <api version, defaults to latest known> \
                  --query <excel file, json file, or raw json> \
                  --output-format <csv, xls, xlsx, json, markdown, sql> \
                  --output <file name or SQL database URL>
```

There are example query files for the CommCare Demo App (available on the CommCareHq Exchange) in the `examples/`
directory.


Python Library Usage
--------------------

As a library, the various `commcare_export` modules make it easy to load and save JSON queries and interact with
the CommCareHq REST API.

To directly access the CommCareHq REST API:

```python
>>> import getpass
>>> from commcare_export.commcare_hq_client import CommCareHqClient
>>> api_client = CommCareHqClient('http://commcarehq.org', domain='your_domain').authenticated('your_username', getpass.getpass())
>>> forms = api_client.iterate('form', {'app_id': "whatever"})
>>> [ (form['received_on'], form['form.gender']) for form in forms ]
```

To issue a `minilinq` query against it, and then print out that query in a JSON serialization:

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
        ]
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

 - `csv`: Each table will be a CSV file within a Zip archive.
 - `xls`: Each table will be a sheet in an old-format Excel spreadsheet.
 - `xlsx`: Each table will be a sheet in a new-format Excel spreadsheet.
 - `json`: The tables will each be a member of a JSON dictionary, printed to standard output
 - `markdown`: The tables will be streamed to standard output in Markdown format (very handy for debugging your queries)
 - `sql`: All data will be idempotently "upserted" into the SQL database you specify, including creating the needed tables and columns.


Dependencies
------------

Required dependencies will be automatically installed via pip. But since
you may not care about all export formats, the various dependencies there
are optional. Here is how you might install them:

```
# To export "xlsx"
$ pip install openpyxl

# To export "xls"
$ pip install xlwt

# To sync with a SQL database
$ pip install SQLAlchemy alembic
```

