Testing and Test Databases
--------------------------

The following command will run the entire test suite (requires DB environment variables to be set as per below):

```shell
$ py.test
```

To run an individual test class or method you can run, e.g.:

```shell
$ py.test -k "TestExcelQuery"
$ py.test -k "test_get_queries_from_excel"
```

To exclude the database tests you can run:

```shell
$ py.test -m "not dbtest"
```

When running database tests, supported databases are PostgreSQL, MySQL, MSSQL.

To run tests against selected databases can be done using test marks as follows:
```shell
$ py.test -m [postgres,mysql,mssql]
```

Use Docker and docker-compose to start database services for tests:

1. Start the services:
   ```shell
   docker-compose up -d
   ```

2. Wait for services to be healthy:
   ```shell
   docker-compose ps
   ```

3. Run your tests. The default environment variables in
   `tests/conftest.py` work automatically:
   - PostgreSQL: `postgresql://postgres@localhost/`
   - MySQL: `mysql+pymysql://travis@/`
   - MS SQL Server: `mssql+pyodbc://SA:Password-123@localhost/`

   If needed, you can override with environment variables:
   ```shell
   export POSTGRES_URL='postgresql://postgres@localhost/'
   export MYSQL_URL='mysql+pymysql://root@localhost/'
   export MSSQL_URL='mssql+pyodbc://SA:Password-123@localhost/'
   ```
4. Stop the services when done:
   ```shell
   docker-compose down
   ```
   To also remove the data volumes:
   ```shell
   docker-compose down -v
   ```

> [!NOTE]
> For MS SQL Server tests, you'll need the ODBC Driver for SQL Server
> installed on your host system for the `pyodbc` connection to work.

From [learn.microsoft.com](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)
([source](https://github.com/MicrosoftDocs/sql-docs/blob/live/docs/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server.md))

#### Debian/Ubuntu

```shell
# Download the package to configure the Microsoft repo
curl -sSL -O https://packages.microsoft.com/config/debian/$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2 | cut -d '.' -f 1)/packages-microsoft-prod.deb
# Install the package
sudo dpkg -i packages-microsoft-prod.deb
# Delete the file
rm packages-microsoft-prod.deb

sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18

odbcinst -q -d
```

#### Mac OS

```shell
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18
```


Integration Tests
-----------------
Running the integration tests requires API credentials from CommCare HQ
that have access to the `corpora` domain. This user should only have
access to the corpora domain.

These need to be set as environment variables as follows:

```shell
$ export HQ_USERNAME=<username>
$ export HQ_API_KEY=<apikey>
```

For Travis builds these are included as encrypted vars in the travis
config.
