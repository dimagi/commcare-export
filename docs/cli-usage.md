Command-line Usage
==================

For comprehensive command-line instructions, see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Run-a-CommCare-Export).


Basic Usage
-----------

```shell
commcare-export \
    --username <username> \
    --project <project> \
    --query <excel or json file> \
    --output-format <csv, xls, xlsx, json, markdown, sql> \
    --output <file name or SQL database URL>
```

See `commcare-export --help` for the full list of options.


Logging
-------

By default, `commcare-export` writes logs to `commcare_export.log` in
the current working directory. Log entries are appended across runs.

```shell
# Custom log directory
commcare-export --log-dir /path/to/logs --query my-query.xlsx --project myproject

# Disable file logging (console only)
commcare-export --no-logfile --query my-query.xlsx --project myproject
```

> [!NOTE]
> The log directory will be created automatically if it doesn't exist.
> If the directory cannot be created or written to, `commcare-export`
> will fall back to console-only logging with a warning.


Database Output
---------------

The `--output` option accepts a SQLAlchemy
[connection string](http://docs.sqlalchemy.org/en/latest/core/engines.html)
following [RFC-1738](https://www.ietf.org/rfc/rfc1738.txt):

```
postgresql+psycopg2://user:password@localhost/mydatabase
mysql+pymysql://user:password@localhost/mydatabase
mssql+pyodbc://user:password@localhost/mydatabase?driver=ODBC+Driver+17+for+SQL+Server
```

For more connection string examples, see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Generating-Database-Connection-Strings).
