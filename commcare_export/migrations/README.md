## Migrations

Migrations use [alembic](http://alembic.zzzcomputing.com/en/latest).

**Create new migration**

```
$ alembic -c commcare_export/migrations/alembic.ini revision -m "description"
```


**Run migrations from command line**

```
$ alembic -c commcare_export/migrations/alembic.ini -x "url=<db url>" upgrade <version e.g. 'head'>
```
