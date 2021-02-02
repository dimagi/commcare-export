CommCare Export
===============

https://github.com/dimagi/commcare-export 

[![Build Status](https://travis-ci.com/dimagi/commcare-export.png)](https://travis-ci.com/dimagi/commcare-export)
[![Test coverage](https://coveralls.io/repos/dimagi/commcare-export/badge.png?branch=master)](https://coveralls.io/r/dimagi/commcare-export)
[![PyPI version](https://badge.fury.io/py/commcare-export.svg)](https://badge.fury.io/py/commcare-export)

A command-line tool (and Python library) to generate customized exports from the [CommCareHQ](https://www.commcarehq.org) [REST API](https://wiki.commcarehq.org/display/commcarepublic/Data+APIs).

* [User documentation](https://wiki.commcarehq.org/display/commcarepublic/CommCare+Data+Export+Tool)
* [Changelog](https://github.com/dimagi/commcare-export/releases)

Installation & Quick Start
--------------------------

0a\. Install Python and `pip`. This tool is [tested with Python 2.7, 3.6 and 3.7](https://travis-ci.com/dimagi/commcare-export).

0b\. Sign up for [CommCareHQ](https://www.commcarehq.org/) if you have not already.

1\. Install CommCare Export via `pip`

```
$ pip install commcare-export
```

2\. Create a project space and application.

3\. Visit the Release Manager, make a build, click the star to release it.

4\. Use Web Apps and fill out some forms.

5\. Modify one of example queries in the `examples/` directory, modifying the "Filter Value" column
    to match your form XMLNS / case type. 
    See [this page](https://confluence.dimagi.com/display/commcarepublic/Finding+a+Form%27s+XMLNS) to 
    determine the XMLNS for your form.

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

All examples are present in Excel and also equivalent JSON, however it is recommended
to use the Excel format as the JSON format may change upon future library releases.

Command-line Usage
------------------

The basic usage of the command-line tool is with a saved Excel or JSON query (see how to write these, below)

```
$ commcare-export --commcare-hq <URL or alias like "local" or "prod"> \
                  --username <username> \
                  --project <project> \
                  --api-version <api version, defaults to latest known> \
                  --version <print current version> \
                  --query <excel file, json file, or raw json> \
                  --output-format <csv, xls, xlsx, json, markdown, sql> \
                  --output <file name or SQL database URL> \
                  --users <export data about project's mobile workers> \
                  --locations <export data about project's location hierarchy> \
                  --with-organization <export users, locations and joinable form or case tables>
```

See `commcare-export --help` for the full list of options.

There are example query files for the CommCare Demo App (available on the CommCareHq Exchange) in the `examples/`
directory.

`--output`

CommCare Export uses SQLAlachemy's [create_engine](http://docs.sqlalchemy.org/en/latest/core/engines.html) to establish a database connection. This is based off of the [RFC-1738](https://www.ietf.org/rfc/rfc1738.txt) protocol. Some common examples:

```
# Postgres
postgresql+psycopg2://scott:tiger@localhost/mydatabase

# MySQL
mysql+pymysql://scott:tiger@localhost/mydatabase

# MSSQL
mssql+pyodbc://scott:tiger@localhost/mydatabases?driver=ODBC+Driver+17+for+SQL+Server
```


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


User and Location Data
----------------------

The --users and --locations options export data from a CommCare project that
can be joined with form and case data. The --with-organization option does all
of that and adds a field to Excel query specifications to be joined on.

Specifiying the --users option or --with-organization option will export an
additional table named 'commcare_users' containing the following columns:

Column                           | Type | Note
------                           | ---- | ----
id                               | Text | Primary key
default_phone_number             | Text |
email                            | Text |
first_name                       | Text |
groups                           | Text |
last_name                        | Text |
phone_numbers                    | Text |
resource_uri                     | Text |
commcare_location_id             | Text | Foreign key into the commcare_locations table
commcare_location_ids            | Text |
commcare_primary_case_sharing_id | Text |
commcare_project                 | Text |
username                         | Text |

The data in the 'commcare_users' table comes from the [List Mobile Workers
API endpoint](https://confluence.dimagi.com/display/commcarepublic/List+Mobile+Workers).

Specifying the --locations option or --with-organization options will export
an additional table named 'commcare_locations' containing the following columns:

Column                       | Type | Note
------                       | ---- | ----
id                           | Text |
created_at                   | Date |
domain                       | Text |
external_id                  | Text |
last_modified                | Date |
latitude                     | Text |
location_data                | Text |
location_id                  | Text | Primary key
location_type                | Text |
longitude                    | Text |
name                         | Text |
parent                       | Text | Resource URI of parent location
resource_uri                 | Text |
site_code                    | Text |
location_type_administrative | Text |
location_type_code           | Text |
location_type_name           | Text |
location_type_parent         | Text |
*location level code*        | Text | Column name depends on project's organization
*location level code*        | Text | Column name depends on project's organization

The data in the 'commcare_locations' table comes from the Location API
endpoint along with some additional columns from the Location Type API
endpoint. The last columns in the table exist if you have set up
organization levels for your projects. One column is created for each
organization level. The column name is derived from the Location Type
that you specified. The column value is the location_id of the containing
location at that level of your organization. Consider the example organization
from the [CommCare help page](https://confluence.dimagi.com/display/commcarepublic/Setting+up+Organization+Levels+and+Structure).
A piece of the 'commcare_locations' table could look like this:

location_id | location_type_name | chw    | supervisor | clinic | district
----------- | ------------------ | ------ | ---------- | ------ | --------
939fa8      | District           | NULL   | NULL       | NULL   | 939fa8
c4cbef      | Clinic             | NULL   | NULL       | c4cbef | 939fa8
a9ca40      | Supervisor         | NULL   | a9ca40     | c4cbef | 939fa8
4545b9      | CHW                | 4545b9 | a9ca40     | c4cbef | 939fa8

In order to join form or case data to 'commcare_users' and 'commcare_locations'
the exported forms and cases need to contain a field identifying which user
submitted them. The --with-organization option automatically adds a field
called 'commcare_userid' to each query in an Excel specifiction for this
purpose. Using that field, you can use a SQL query with a join to report
data about any level of you organization. For example, to count the number
of forms submitted by all workers in each clinic:

```sql
SELECT l.clinic,
       COUNT(*)
FROM form_table t
LEFT JOIN (commcare_users u
           LEFT JOIN commcare_locations l
           ON u.commcare_location_id = l.location_id)
ON t.commcare_userid = u.id
GROUP BY l.clinic;
```

Note that the table names 'commcare_users' and 'commcare_locations' are
treated as reserved names and the export tool will produce an error if
given a query specification that writes to either of them.

The export tool will write all users to 'commcare_users' and all locations to
'commcare_locations', overwriting existing rows with current data and adding
rows for new users and locations. If you want to remove obsolete users or
locations from your tables, drop them and the next export will leave only
the current ones. If you modify your organization to add or delete levels,
you will change the columns of the 'commcare_locations' table and it is
very likely you will want to drop the table before exporting with the new
organization.

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
>>> api_client = CommCareHqClient('http://commcarehq.org', 'your_project', 'your_username', getpass.getpass())
>>> forms = api_client.iterate('form', {'app_id': "whatever"})
>>> [ (form['received_on'], form['form.gender']) for form in forms ]
```

To issue a `minilinq` query against it, and then print out that query in a JSON serialization:

```python
import getpass
import json
from commcare_export.minilinq import *
from commcare_export.commcare_hq_client import CommCareHqClient
from commcare_export.commcare_minilinq import CommCareHqEnv
from commcare_export.env import BuiltInEnv

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

print json.dumps(query.to_jvalue(), indent=2)

results = query.eval(BuiltInEnv() | CommCareHqEnv(api_client) | JsonPathEnv())

if len(list(env.emitted_tables())) > 0:
    # with writers.Excel2007TableWriter("excel-output.xlsx") as writer:
    with writers.StreamingMarkdownTableWriter(sys.stdout) as writer:
        for table in env.emitted_tables():
            writer.write_table(table)
```

Which will output JSON equivalent to this:

```javascript
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
                "name": None,
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


MiniLinq Reference
------------------

The abstract syntax can be directly inspected in the `commcare_export.minilinq` module. Note that the choice between functions and primitives is deliberately chosen
to expose the structure of the MiniLinq for possible optimization, and to restrict the overall language.

Here is a description of the astract syntax and semantics

| Python                        | JSON                                                | Which is evaluates to            |
|-------------------------------|-----------------------------------------------------|----------------------------------|
| `Literal(v)`                  | `{"Lit": v}`                                        | Just `v`                         |
| `Reference(x)`                | `{"Ref": x}`                                        | Whatever `x` resolves to in the environment |
| `List([a, b, c, ...])`        | `{"List": [a, b, c, ...}`                           | The list of what `a`, `b`, `c` evaluate to |
| `Map(source, name, body)`     | `{"Map": {"source": ..., "name": ..., "body": ...}` | Evals `body` for each elem in `source`. If `name` is provided, the elem will be bound to it, otherwise it will replace the whole env. |
| `FlatMap(source, name, body)` | `{"FlatMap": {"source" ... etc}}` | Flattens after mapping, like nested list comprehensions |
| `Filter(source, name, body)`  | etc | |
| `Bind(value, name, body)`     | etc | Binds the result of `value` to `name` when evaluating `body` |
| `Emit(table, headings, rows)` | etc | Emits `table` with `headings` and `rows`. Note that `table` is a string, `headings` is a list of expressions, and `rows` is a list of lists of expressions. See explanation below for emitted output. |
| `Apply(fn, args)` | etc | Evaluates `fn` to a function, and all of `args`, then applies the function to the args. |

Built in functions like `api_data` and basic arithmetic and comparison are provided via the environment,
referred to be name using `Ref`, and utilized via `Apply`.

List of builtin functions:

| Function                       | Description                                                                    | Example Usage                    |
|--------------------------------|--------------------------------------------------------------------------------|----------------------------------|
| `+, -, *, //, /, >, <, >=, <=` | Standard Math                                                                  |                                  |
| len                          | Length                                                                         |                                  |
| bool                         | Bool                                                                           |                                  |
| str2bool                     | Convert string to boolean. True values are 'true', 't', '1' (case insensitive) |                                  |
| str2date                     | Convert string to date                                                         |                                  |
| bool2int                     | Convert boolean to integer (0, 1)                                              |                                  |
| str2num                      | Parse string as a number                                                       |                                  |
| format-uuid                  | Parse a hex UUID, and format it into hyphen-separated groups                   |                                  |
| substr                       | Returns substring indexed by [first arg, second arg), zero-indexed.            | substr(2, 5) of 'abcdef' = 'cde' |
| selected-at                  | Returns the Nth word in a string. N is zero-indexed.                           | selected-at(3) - return 4th word |
| selected                     | Returns True if the given word is in the value.                                | selected(fever)                  |
| count-selected               | Count the number of words                                                      |                                  |
| json2str                     | Convert a JSON object to a string                                              |
| template                     | Render a string template (not robust)                                          | template({} on {}, state, date)  |
| attachment_url               | Convert an attachment name into it's download URL                              |                                  |
| form_url                     | Output the URL to the form view on CommCare HQ                                 |                                  |
| case_url                     | Output the URL to the case view on CommCare HQ                                 |                                  |

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
$ pip install SQLAlchemy alembic psycopg2 pymysql pyodbc
```

Contributing
------------

0\. Sign up for github, if you have not already, at https://github.com.

1\. Fork the repository at https://github.com/dimagi/commcare-export.

2\. Clone your fork, install into a `virtualenv`, and start a feature branch

```
$ mkvirtualenv commcare-export
$ git clone git@github.com:dimagi/commcare-export.git
$ cd commcare-export
$ pip install -e ".[test]"
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
$ git push -u origin my-super-duper-feature
```

6\. Visit https://github.com/dimagi/commcare-export and submit a pull request.

7\. Accept our gratitude for contributing: Thanks!

Release process
---------------

1\. Create a tag for the release

```
$ git tag -a "X.YY.0" -m "Release X.YY.0"
$ git push --tags
```

2\. Create the source distribution

```
$ python setup.py sdist
```
Ensure that the archive (`dist/commcare-export-X.YY.0.tar.gz`) has the correct version number (matching the tag name).

3\. Upload to pypi

```
$ pip install twine
$ twine upload -u dimagi dist/commcare-export-X.YY.0.tar.gz
```

4\. Verify upload

https://pypi.python.org/pypi/commcare-export

5\. Create a release on github

https://github.com/dimagi/commcare-export/releases


Testing and Test Databases
--------------------------

The following command will run the entire test suite (requires DB environment variables to be set as per below):

```
$ py.test
```

To run an individual test class or method you can run, e.g.:

```
$ py.test -k "TestExcelQuery"
$ py.test -k "test_get_queries_from_excel"
```

To exclude the database tests you can run:

```
$ py.test -m "not dbtest"
```

When running database tests, supported databases are PostgreSQL, MySQL, MSSQL.

To run tests against selected databases can be done using test marks as follows:
```
py.test -m [postgres,mysql,mssql]
```

Database URLs can be overridden via environment variables:
```
POSTGRES_URL=postgresql://user:password@host/
MYSQL_URL=mysql+pymysql://user:password@host/
MSSQL_URL=mssql+pyodbc://user:password@host/
```

Postgresql
==========
```
$ docker pull postgres:9.6
$ docker run --name ccexport-postgres -p 5432:5432 -e POSTGRES_PASSWORD=postgres -d postgres:9.6
$ export POSTGRES_URL=postgresql://postgres:postgres@localhost/
```

[Docker postgres image docs](https://hub.docker.com/_/postgres/)

MySQL
=====
```
$ docker pull mysql
$ docker run --name ccexport-mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=pw -e MYSQL_USER=travis -e MYSQL_PASSWORD='' -d mysql

# create travis user
$ docker run -it --link ccexport-mysql:mysql --rm mysql sh -c 'exec mysql -h"$MYSQL_PORT_3306_TCP_ADDR" -P"$MYSQL_PORT_3306_TCP_PORT" -uroot -p"$MYSQL_ENV_MYSQL_ROOT_PASSWORD"'
mysql> CREATE USER 'travis'@'%';
mysql> GRANT ALL PRIVILEGES ON *.* TO 'travis'@'%';
```

MSSQL
=====
```
$ docker pull microsoft/mssql-server-linux:2017-latest
$ docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Password@123" -p 1433:1433 --name mssql1 -d microsoft/mssql-server-linux:2017-latest

# install driver
$ curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
$ echo "deb [arch=amd64] https://packages.microsoft.com/ubuntu/$(lsb_release -rs)/prod $(lsb_release -rs) main" | sudo tee /etc/apt/sources.list.d/mssql-release.list

$ sudo apt-get update
$ sudo ACCEPT_EULA=Y apt-get install msodbcsql17
$ odbcinst -q -d
```

MSSQL for Mac OS
==========
```
$ docker pull microsoft/mssql-server-linux:2017-latest
$ docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Password@123" -p 1433:1433 --name mssql1 -d microsoft/mssql-server-linux:2017-latest

# Install driver
$ brew install unixodbc freetds

# Add the following 5 lines to /usr/local/etc/odbcinst.ini
[ODBC Driver 17 for SQL Server]
Description=FreeTDS Driver for Linux & MSSQL
Driver=/usr/local/lib/libtdsodbc.so
Setup=/usr/local/lib/libtdsodbc.so
UsageCount=1

# Create a soft link from /etc/odbcinst.ini to actual file
sudo ln -s /usr/local/etc/odbcinst.ini /etc/odbcinst.ini

```

Integration Tests
-----------------
Running the integration tests requires API credentials from CommCare HQ
that have access to the `corpora` domain. This user should only have
access to the corpora domain.

These need to be set as environment variables as follows:

```
export HQ_USERNAME=<username>
export HQ_API_KEY=<apikey>
```

For Travis builds these are included as encrypted vars in the travis
config.
