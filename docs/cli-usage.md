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
