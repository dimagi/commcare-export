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

See [docs/cli-usage.md](docs/cli-usage.md).

Query Formats
-------------

See [docs/query-formats.md](docs/query-formats.md).

User and Location Data
----------------------

See [docs/user-location-data.md](docs/user-location-data.md).

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
