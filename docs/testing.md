Testing Guide
=============

*Part of [Technical Documentation](index.md)*

This guide covers running tests for CommCare Export, including setup for
database tests.


Running Tests
-------------

### Full Test Suite

To run the entire test suite (requires database environment variables to
be set):

```shell
pytest
```

### Individual Tests

To run an individual test class or method:

```shell
# Run a specific test class
pytest -k "TestExcelQuery"

# Run a specific test method
pytest -k "test_get_queries_from_excel"
```

### Excluding Database Tests

To exclude the database tests:

```shell
pytest -m "not dbtest"
```


Database Tests
--------------

CommCare Export supports testing against PostgreSQL, MySQL, and MS SQL
Server.

### Running Database-Specific Tests

To run tests against specific databases using test marks:

```shell
# PostgreSQL tests only
pytest -m postgres

# MySQL tests only
pytest -m mysql

# MS SQL Server tests only
pytest -m mssql

# Multiple databases
pytest -m "postgres or mysql"
```


Database Setup with Docker
--------------------------

Use Docker and docker-compose to start database services for tests.

### Starting Services

1. Start the database services:
   ```shell
   docker-compose up -d
   ```

2. Wait for services to be healthy:
   ```shell
   docker-compose ps
   ```

   Wait until all services show "healthy" status.

3. Run your tests (default environment variables work automatically):
   ```shell
   pytest
   ```

### Database Connection Defaults

The default environment variables in `tests/conftest.py` work
automatically with Docker Compose:

- **PostgreSQL**: `postgresql://postgres@localhost/`
- **MySQL**: `mysql+pymysql://travis@/`
- **MS SQL Server**: `mssql+pyodbc://SA:Password-123@localhost/`

### Custom Database URLs

If needed, you can override with environment variables:

```shell
export POSTGRES_URL='postgresql://postgres@localhost/'
export MYSQL_URL='mysql+pymysql://root@localhost/'
export MSSQL_URL='mssql+pyodbc://SA:Password-123@localhost/'
```

### Stopping Services

Stop the services when done:

```shell
docker-compose down
```

To also remove the data volumes:

```shell
docker-compose down -v
```


ODBC Driver Installation
------------------------

For MS SQL Server tests, you'll need the ODBC Driver for SQL Server
installed on your host system for the `pyodbc` connection to work.

### Debian/Ubuntu

From [learn.microsoft.com](https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server):

```shell
# Download the package to configure the Microsoft repo
curl -sSL -O https://packages.microsoft.com/config/debian/$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2 | cut -d '.' -f 1)/packages-microsoft-prod.deb

# Install the package
sudo dpkg -i packages-microsoft-prod.deb

# Delete the file
rm packages-microsoft-prod.deb

# Update and install
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Verify installation
odbcinst -q -d
```

### macOS

```shell
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"

# Add Microsoft tap
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release

# Update and install
brew update
HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18
```


Writing Tests
-------------

### Basic Test Structure

```python
import pytest
from commcare_export.minilinq import Literal, Reference

def test_my_feature():
    # Arrange
    query = Literal("test")

    # Act
    result = query.eval({})

    # Assert
    assert result == "test"
```

### Database Tests

Mark tests that require a database:

```python
@pytest.mark.dbtest
@pytest.mark.postgres
def test_postgres_export(postgres_db):
    # Test code here
    pass
```


Continuous Integration
----------------------

### GitHub Actions

Tests run automatically on:
- Every push to any branch
- Every pull request
- Multiple Python versions (3.9, 3.10, 3.11, 3.12, 3.13)
- Multiple platforms (Ubuntu, macOS, Windows)


Troubleshooting
---------------

### Database Connection Failures

**Problem:** Can't connect to test databases

**Solutions:**
- Ensure Docker services are running: `docker-compose ps`
- Check database logs: `docker-compose logs postgres`
- Verify ports aren't in use: `lsof -i :5432` (PostgreSQL)
- Restart services: `docker-compose restart`

### ODBC Driver Issues

**Problem:** pyodbc can't find SQL Server driver

**Solutions:**
- Verify driver is installed: `odbcinst -q -d`
- Install correct driver version (see ODBC installation above)
- Check connection string format matches driver name

### Database Server Unavailable

**Problem:** A particular database server is not available

**Solutions:**
- Skip tests for a particular database server: `pytest -m "not mssql"`


See Also
--------

- [Development Guide](development.md) - Setting up development
  environment
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Contributing guidelines
- [Database Integration](database-integration.md) - Database usage
  documentation
