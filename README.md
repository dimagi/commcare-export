CommCare Export
===============

https://github.com/dimagi/commcare-export 

[![Build Status](https://github.com/dimagi/commcare-export/actions/workflows/test.yml/badge.svg)](https://github.com/dimagi/commcare-export/actions)
[![Test coverage](https://coveralls.io/repos/dimagi/commcare-export/badge.png?branch=master)](https://coveralls.io/r/dimagi/commcare-export)
[![PyPI version](https://badge.fury.io/py/commcare-export.svg)](https://badge.fury.io/py/commcare-export)

A command-line tool (and Python library) to generate customized exports from the [CommCare HQ](https://www.commcarehq.org) [REST API](https://wiki.commcarehq.org/display/commcarepublic/Data+APIs).

* [User documentation](https://wiki.commcarehq.org/display/commcarepublic/CommCare+Data+Export+Tool)
* [Changelog](https://github.com/dimagi/commcare-export/releases)

Installation & Quick Start
--------------------------

Following commands are to be run on a terminal or a command line.

Once on a terminal window or command line, for simplicity, run commands from the home directory.

### Python

Check which Python version is installed.

This tool is tested with Python versions from 3.9 to 3.13.

```shell
$ python3 --version
```
If Python is installed, its version will be shown.

If Python isn't installed, [download and install](https://www.python.org/downloads/)
a version of Python from 3.9 to 3.13.

## Virtualenv (Optional)

It is recommended to set up a virtual environment for CommCare Export
to avoid conflicts with other Python applications.

More about virtualenvs on https://docs.python.org/3/tutorial/venv.html

Setup a virtual environment using:

```shell
$ python3 -m venv venv
```

Activate virtual environment by running:

```shell
$ source venv/bin/activate
```

**Note**: virtualenv needs to be activated each time you start a new terminal session or command line prompt.

For convenience, to avoid doing that, you can create an alias to activate virtual environments in
"venv" directory by adding the following to your
`.bashrc` or `.zshrc` file:

```shell
$ alias venv='if [[ -d venv ]] ; then source venv/bin/activate ; fi'
```

Then you can activate virtual environments with simply typing
```shell
$ venv
```

## Install CommCare Export

[uv](https://docs.astral.sh/uv/) is a fast Python package installer and resolver.

```shell
$ uv pip install commcare-export
```

## CommCare HQ

1. Sign up for [CommCare HQ](https://www.commcarehq.org/) if you have not already.

2. Create a project space and application.

3. Visit the Release Manager, make a build, click the star to release it.

4. Use Web Apps and fill out some forms.

5. Modify one of example queries in the `examples/` directory, modifying the "Filter Value" column
    to match your form XMLNS / case type. 
    See [this page](https://confluence.dimagi.com/display/commcarepublic/Finding+a+Form%27s+XMLNS) to 
    determine the XMLNS for your form.

Now you can run the following examples:

```shell
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

Example query files are provided in both Excel and JSON format.  It is recommended
to use the Excel format as the JSON format may change upon future library releases.

Command-line Usage
------------------

The basic usage of the command-line tool is with a saved Excel or JSON query (see how to write these, below)

```shell
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

### Logging

By default, commcare-export writes logs to a file named
`commcare_export.log` in the current working directory. Log entries are
appended to this file across multiple runs to preserve history.

You can customize the log directory:

```shell
$ commcare-export --log-dir /path/to/logs \
     --query my-query.xlsx \
     --project myproject
```

To disable file logging and show all output in the console only:

```shell
$ commcare-export --no-logfile \
     --query my-query.xlsx \
     --project myproject
```

> [!NOTE]
> The log directory will be created automatically if it doesn't exist.
> If the specified directory cannot be created or written to,
> commcare-export will fall back to console-only logging with a warning
> message.

There are example query files for the CommCare Demo App (available on the CommCare HQ Exchange) in the `examples/`
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

An Excel query is any `.xlsx` workbook. Each sheet in the workbook represents one table you wish
to create. There are two grouping of columns to configure the table:

 - **Data Source**: Set this to `form` to export form data, or `case` for case data.
 - **Filter Name** / *Filter Value*: These columns are paired up to filter the input cases or forms.
 - **Field**: The destination in your SQL database for the value.
 - **Source Field**: The particular field from the form you wish to extract. This can be any JSON path.


JSON Queries
------------

JSON queries are a described in the table below. You build a JSON object that represents the query you have in mind.
A good way to get started is to work from the examples, or you could make an Excel query and run the tool
with `--dump-query` to see the resulting JSON query.


User and Location Data
----------------------

The --users and --locations options export data from a CommCare project that
can be joined with form and case data. The --with-organization option does all
of that and adds a field to Excel query specifications to be joined on.

Specifying the --users option or --with-organization option will export an
additional table named 'commcare_users' containing the following columns:

| Column                           | Type | Note                                |
|----------------------------------|------|-------------------------------------|
| id                               | Text | Primary key                         |
| default_phone_number             | Text |                                     |
| email                            | Text |                                     |
| first_name                       | Text |                                     |
| groups                           | Text |                                     |
| last_name                        | Text |                                     |
| phone_numbers                    | Text |                                     |
| resource_uri                     | Text |                                     |
| commcare_location_id             | Text | Foreign key to `commcare_locations` |
| commcare_location_ids            | Text |                                     |
| commcare_primary_case_sharing_id | Text |                                     |
| commcare_project                 | Text |                                     |
| username                         | Text |                                     |

The data in the 'commcare_users' table comes from the [List Mobile Workers
API endpoint](https://confluence.dimagi.com/display/commcarepublic/List+Mobile+Workers).

Specifying the --locations option or --with-organization options will export
an additional table named 'commcare_locations' containing the following columns:

| Column                       | Type | Note                                          |
|------------------------------|------|-----------------------------------------------|
| id                           | Text |                                               |
| created_at                   | Date |                                               |
| domain                       | Text |                                               |
| external_id                  | Text |                                               |
| last_modified                | Date |                                               |
| latitude                     | Text |                                               |
| location_data                | Text |                                               |
| location_id                  | Text | Primary key                                   |
| location_type                | Text |                                               |
| longitude                    | Text |                                               |
| name                         | Text |                                               |
| parent                       | Text | Resource URI of parent location               |
| resource_uri                 | Text |                                               |
| site_code                    | Text |                                               |
| location_type_administrative | Text |                                               |
| location_type_code           | Text |                                               |
| location_type_name           | Text |                                               |
| location_type_parent         | Text |                                               |
| *location level code*        | Text | Column name depends on project's organization |
| *location level code*        | Text | Column name depends on project's organization |

The data in the 'commcare_locations' table comes from the Location API
endpoint along with some additional columns from the Location Type API
endpoint. The last columns in the table exist if you have set up
organization levels for your projects. One column is created for each
organization level. The column name is derived from the Location Type
that you specified. The column value is the location_id of the containing
location at that level of your organization. Consider the example organization
from the [CommCare help page](https://confluence.dimagi.com/display/commcarepublic/Setting+up+Organization+Levels+and+Structure).
A piece of the 'commcare_locations' table could look like this:

| location_id | location_type_name | chw    | supervisor | clinic | district |
|-------------|--------------------|--------|------------|--------|----------|
| 939fa8      | District           | NULL   | NULL       | NULL   | 939fa8   |
| c4cbef      | Clinic             | NULL   | NULL       | c4cbef | 939fa8   |
| a9ca40      | Supervisor         | NULL   | a9ca40     | c4cbef | 939fa8   |
| 4545b9      | CHW                | 4545b9 | a9ca40     | c4cbef | 939fa8   |

In order to join form or case data to 'commcare_users' and 'commcare_locations'
the exported forms and cases need to contain a field identifying which user
submitted them. The --with-organization option automatically adds a field
called 'commcare_userid' to each query in an Excel specification for this
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

Scheduling the DET
------------------

See [docs/scheduling.md](docs/scheduling.md).

Python Library Usage
--------------------

See [docs/library-usage.md](docs/library-usage.md).

MiniLinq Reference
------------------

See [docs/minilinq-reference.md](docs/minilinq-reference.md).

Output Formats and Dependencies
-------------------------------

See [docs/output-formats.md](docs/output-formats.md).

Contributing
------------

See [CONTRIBUTING.md](CONTRIBUTING.md).

Testing
-------

See [docs/testing.md](docs/testing.md).
