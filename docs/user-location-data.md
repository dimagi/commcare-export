User and Location Data
======================

*Part of [Technical Documentation](index.md)*

CommCare Export can export user and location data from your CommCare
project, which can be joined with form and case data for organizational
reporting.


Overview
--------

The `--users` and `--locations` options export data from a CommCare
project that can be joined with form and case data. The
`--with-organization` option does all of that and adds a field to Excel
query specifications to be joined on.


Exporting Users
---------------

### Basic Usage

```shell
commcare-export --project myproject \
  --users \
  --output-format sql \
  --output postgresql://user:pass@localhost/mydb
```

### User Table Schema

Specifying the `--users` option or `--with-organization` option will
export an additional table named `commcare_users` containing the
following columns:

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

### Data Source

The data in the `commcare_users` table comes from the
[List Mobile Workers API endpoint](https://confluence.dimagi.com/display/commcarepublic/List+Mobile+Workers).


Exporting Locations
-------------------

### Basic Usage

```shell
commcare-export --project myproject \
  --locations \
  --output-format sql \
  --output postgresql://user:pass@localhost/mydb
```

### Location Table Schema

Specifying the `--locations` option or `--with-organization` options
will export an additional table named `commcare_locations` containing
the following columns:

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

### Organization Level Columns

The last columns in the table exist if you have set up organization
levels for your projects. One column is created for each organization
level. The column name is derived from the Location Type that you
specified. The column value is the location_id of the containing
location at that level of your organization.

Consider the example organization from the
[CommCare help page](https://confluence.dimagi.com/display/commcarepublic/Setting+up+Organization+Levels+and+Structure).
A piece of the `commcare_locations` table could look like this:

| location_id | location_type_name | chw    | supervisor | clinic | district |
|-------------|--------------------|--------|------------|--------|----------|
| 939fa8      | District           | NULL   | NULL       | NULL   | 939fa8   |
| c4cbef      | Clinic             | NULL   | NULL       | c4cbef | 939fa8   |
| a9ca40      | Supervisor         | NULL   | a9ca40     | c4cbef | 939fa8   |
| 4545b9      | CHW                | 4545b9 | a9ca40     | c4cbef | 939fa8   |

### Data Source

The data in the `commcare_locations` table comes from the Location API
endpoint along with some additional columns from the Location Type API
endpoint.


Exporting with Organization Data
--------------------------------

The `--with-organization` option combines user, location, and form/case
exports, automatically adding a `commcare_userid` field for joining.

### Basic Usage

```shell
commcare-export --project myproject \
  --query forms.xlsx \
  --with-organization \
  --output-format sql \
  --output postgresql://user:pass@localhost/mydb
```

### What This Does

1. Exports your form/case data as specified in the query
2. Automatically adds a `commcare_userid` field to each query table
3. Exports the `commcare_users` table
4. Exports the `commcare_locations` table


Joining Data
------------

In order to join form or case data to `commcare_users` and
`commcare_locations`, the exported forms and cases need to contain a
field identifying which user submitted them. The `--with-organization`
option automatically adds a field called `commcare_userid` to each
query in an Excel specification for this purpose.

### Example: Forms by Clinic

Using that field, you can use a SQL query with a join to report data
about any level of your organization. For example, to count the number
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

### Example: Forms by Location Type

```sql
SELECT l.location_type_name,
       COUNT(*) as form_count
FROM form_table t
LEFT JOIN commcare_users u ON t.commcare_userid = u.id
LEFT JOIN commcare_locations l ON u.commcare_location_id = l.location_id
GROUP BY l.location_type_name;
```

### Example: User Details with Forms

```sql
SELECT u.username,
       u.first_name,
       u.last_name,
       COUNT(t.form_id) as submissions
FROM form_table t
LEFT JOIN commcare_users u ON t.commcare_userid = u.id
GROUP BY u.username, u.first_name, u.last_name
ORDER BY submissions DESC;
```


Reserved Table Names
--------------------

Note that the table names `commcare_users` and `commcare_locations` are
treated as reserved names and the export tool will produce an error if
given a query specification that writes to either of them.


Data Refresh Behavior
---------------------

The export tool will write all users to `commcare_users` and all
locations to `commcare_locations`, overwriting existing rows with
current data and adding rows for new users and locations.

### Handling Removed Users/Locations

If you want to remove obsolete users or locations from your tables, drop
them and the next export will leave only the current ones:

```sql
-- Drop and refresh users table
DROP TABLE commcare_users;
# Run export again

-- Drop and refresh locations table
DROP TABLE commcare_locations;
# Run export again
```

### Handling Organization Changes

If you modify your organization to add or delete levels, you will change
the columns of the `commcare_locations` table and it is very likely you
will want to drop the table before exporting with the new
organization:

```sql
DROP TABLE commcare_locations;
```

Then run your export again to recreate the table with the new structure.


Incremental Updates
-------------------

When using SQL output format with checkpoints:

- **Form/case data**: Incremental updates based on checkpoints
- **User data**: Full refresh on every run
- **Location data**: Full refresh on every run

This ensures user and location data is always current, while form/case
exports remain efficient.


Use Cases
---------

### Organizational Reporting

Track performance across your organization hierarchy:

```sql
-- Forms per district per month
SELECT l.district,
       DATE_TRUNC('month', t.received_on) as month,
       COUNT(*) as forms
FROM form_table t
LEFT JOIN commcare_users u ON t.commcare_userid = u.id
LEFT JOIN commcare_locations l ON u.commcare_location_id = l.location_id
GROUP BY l.district, DATE_TRUNC('month', t.received_on)
ORDER BY month, l.district;
```

### User Performance

Identify top performers and those needing support:

```sql
-- Forms per user with location context
SELECT u.username,
       u.first_name || ' ' || u.last_name as full_name,
       l.location_type_name,
       l.name as location_name,
       COUNT(*) as forms_submitted
FROM form_table t
LEFT JOIN commcare_users u ON t.commcare_userid = u.id
LEFT JOIN commcare_locations l ON u.commcare_location_id = l.location_id
WHERE t.received_on >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY u.username, full_name, l.location_type_name, l.name
ORDER BY forms_submitted DESC;
```

### Geographic Analysis

When locations have latitude/longitude:

```sql
-- Forms by location with coordinates
SELECT l.name,
       l.latitude,
       l.longitude,
       COUNT(*) as forms
FROM form_table t
LEFT JOIN commcare_users u ON t.commcare_userid = u.id
LEFT JOIN commcare_locations l ON u.commcare_location_id = l.location_id
WHERE l.latitude IS NOT NULL
GROUP BY l.name, l.latitude, l.longitude;
```


Troubleshooting
---------------

### Missing commcare_userid Field

**Problem:** `commcare_userid` column doesn't exist in form/case tables

**Solution:** Use `--with-organization` flag, not just `--users` and
`--locations`

### NULL Values in Joins

**Problem:** Many NULL values when joining to users or locations

**Solutions:**
- Verify forms were submitted by users (not admin forms)
- Check that user IDs in forms match user IDs in commcare_users
- Ensure users table was exported from the same project

### Location Hierarchy Not Showing

**Problem:** Location level columns are NULL or missing

**Solutions:**
- Verify project has organization levels configured in CommCare HQ
- Drop and recreate locations table if organization changed
- Check that users are assigned to locations in CommCare HQ


See Also
--------

- [Database Integration](database-integration.md) - SQL database setup
  and connection
- [Query Formats](query-formats.md) - Creating queries that will include
  commcare_userid
- [CommCare HQ Documentation](https://confluence.dimagi.com/display/commcarepublic/Setting+up+Organization+Levels+and+Structure) -
  Setting up organization levels
