CommCare Export
===============

https://github.com/dimagi/commcare-export 

[![Build status](https://travis-ci.org/dimagi/commcare-export.png)](https://travis-ci.org/dimagi/commcare-export)

A command-line tool (and Python library) to generate customized exports from the CommCareHQ REST API.

Installation & Quick Start
--------------------------

0a\. Install Python and `pip`. This tool is [tested with Python 2.6, 2.7, and 3.3](https://travis-ci.org/dimagi/commcare-export).

0b\. Sign up for CommCareHQ at https://www.commcarehq.org/register/user if you have not already.

1\. Install CommCare Export via `pip`

```
$ pip install commcare-export
```

2\. Visit the CommCareHQ Exchange and add the [Simple CommCare Demo/Tutorial"](https://www.commcarehq.org/exchange/611422532c7ab89d22cca54d57ae89aa/info/) app to a new project space.

3\. Visit the Release Manager, make a build, click the star to release it.

4\. Visit CloudCare and fill out a bunch of forms.

5\. Try out the example queries in the `examples/` directory, providing your project name on the command line:

```
$ commcare-export \
     --query examples/demo-registration.xlsx \
     --project YOUR_PROJECT \
     --output-format markdown

$ commcare-export \
     --query examples/demo-registration.json \
     --project YOUR_PROJECT \
     --output-format markdown

$ commcare-export \
     --query examples/demo-deliveries.xlsx \
     --project YOUR_PROJECT \
     --output-format markdown

$ commcare-export \
     --query examples/demo-deliveries.json \
     --project YOUR_PROJECT \
     --output-format markdown
```

You'll see the tables printed out. Change to `--output-format sql --output URL_TO_YOUR_DB --since DATE` to
sync all forms submitted since that date.

All examples are present in Excel and also equivalent JSON.

Command-line Usage
------------------

The basic usage of the command-line tool is with a saved Excel or JSON query (see how to write these, below)

```
$ commcare-export --commcare-hq <URL or alias like "local" or "prod"> \
                  --username <username> \
                  --project <project> \
                  --version <api version, defaults to latest known> \
                  --query <excel file, json file, or raw json> \
                  --output-format <csv, xls, xlsx, json, markdown, sql> \
                  --output <file name or SQL database URL>
```

See `commcare-export --help` for the full list of options.

There are example query files for the CommCare Demo App (available on the CommCareHq Exchange) in the `examples/`
directory.


Excel Queries
-------------

An excel query is any `.xlsx` workbook. Each sheet in the workbook represents one table you wish
to create. There are two grouping of columns to configure the table:

 - **Data Source**: Set this to `form` to export form data, or `case` for case data.
 - **Filter Name** / *Filter Value*: These columns are paired up to filter the input cases or forms.
 - **Field**: The destination in your SQL database for the value.
 - **Source Field**: The particular field from the form you wish to extract. This can be any JSON path.


JSON Queries
------------

JSON queries are a described in the table below. You build a JSON object that represents the query you have in mind.
A good way to get started is to work from the examples, or you could make an excel query and run the tool
with `--dump-query` to see the resulting JSON query.


Python Library Usage
--------------------

As a library, the various `commcare_export` modules make it easy to

 - Interact with the CommCareHQ REST API
 - Execute "Minilinq" queries against the API (a very simple query language, described below)
 - Load and save JSON representations of Minilinq queries
 - Compile Excel configurations to Minilinq queries

To directly access the CommCareHq REST API:

```python
>>> import getpass
>>> from commcare_export.commcare_hq_client import CommCareHqClient
>>> api_client = CommCareHqClient('http://commcarehq.org', project='your_project').authenticated('your_username', getpass.getpass())
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
>>> api_client = CommCareHqClient('http://commcarehq.org', project='your_project').authenticated('your_username', getpass.getpass())
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

| Python                      | JSON                                                | Which is evaluates to            |
|-----------------------------|-----------------------------------------------------|----------------------------------|
| `Literal(v)`                | `{"Lit": v}`                                        | Just `v`                         |
| `Reference(x)`              | `{"Ref": x}`                                        | Whatever `x` resolves to in the environment |
| `List([a, b, c, ...])`      | `{"List": [a, b, c, ...}`                           | The list of what `a`, `b`, `c` evaluate to |
| `Map(source, name, body)`   | `{"Map": {"source": ..., "name": ..., "body": ...}` | Evals `body` for each elem in `source`. If `name` is provided, the elem will be bound to it, otherwise it will replace the whole env. |
| `FlatMap(source, name, body)` | `{"FlatMap": {"source" ... etc}}` | Flattens after mapping, like nested list comprehensions |
| `Filter(source, name, body)`  | etc | |
| `Bind(value, name, body)`     | etc | Binds the result of `value` to `name` when evaluating `body` |
| `Emit(table, headings, rows)` | etc | Emits `table` with `headings` and `rows`. Note that `table` is a string, `headings` is a list of expressions, and `rows` is a list of lists of expressions. See explanation belowe for emitted output. |
| `Apply(fn, args)` | etc | Evaluates `fn` to a function, and all of `args`, then applies the function to the args. |

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

Contributing
------------

0\. Sign up for github, if you have not already, at https://github.com.

1\. Fork the repository at https://github.com/dimagi/commcare-export.

2\. Clone your fork, install into a `virtualenv`, and start a feature branch

```
$ mkvirtualenv commcare-export
$ git clone git@github.com:YOUR_USERNAME/commcare-export.git
$ cd commcare-export
$ pip install -e .
$ git checkout -b my-super-duper-feature
```

3\. Make your edits.

4\. Make sure the tests pass. The best way to test for all versions is to sign up for https://travis-ci.org and turn on automatic continuous testing for your fork.

```
$ py.test
=============== test session starts ===============
platform darwin -- Python 2.7.3 -- pytest-2.3.4
collected 17 items

tests/test_commcare_minilinq.py .
tests/test_excel_query.py ....
tests/test_minilinq.py ........
tests/test_repeatable_iterator.py .
tests/test_writers.py ...

============ 17 passed in 2.09 seconds ============
```

5\. Push the feature branch up

```
$ git push -u origin my-super-duper-feature`
```

6\. Visit https://github.com/YOUR_USERNAME/commcare-export and submit a pull request.

7\. Accept our gratitude for contributing: Thanks!

