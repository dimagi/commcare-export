User and Location Data
======================

The Data Export Tool can export user and location data from your
CommCare project, which can be joined with form and case data for
organizational reporting.

For detailed usage instructions and examples, see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Exporting-User-and-Location-Data).


Overview
--------

- `--users` exports a `commcare_users` table
- `--locations` exports a `commcare_locations` table
- `--with-organization` exports both tables and adds a
  `commcare_userid` field to each query for joining


User Table Schema
-----------------

The `commcare_users` table contains data from the
[List Mobile Workers API endpoint](https://confluence.dimagi.com/display/commcarepublic/List+Mobile+Workers):

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


Location Table Schema
---------------------

The `commcare_locations` table contains data from the Location API and
Location Type API endpoints:

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

If you have set up
[organization levels](https://confluence.dimagi.com/display/commcarepublic/Setting+up+Organization+Levels+and+Structure),
one additional column is created for each level. The column name is
derived from the Location Type, and the value is the `location_id` of
the containing location at that level.


Joining Data
------------

The `--with-organization` option adds a `commcare_userid` field to each
Excel query. Use this field to join form or case data with user and
location data:

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

> [!NOTE]
> The table names `commcare_users` and `commcare_locations` are reserved.
> The export tool will produce an error if given a query specification
> that writes to either of them.


Data Refresh Behavior
---------------------

The export tool overwrites existing rows with current data and adds rows
for new users and locations. To remove obsolete entries, drop the table
and re-export. If you modify your organization levels, drop the
`commcare_locations` table before re-exporting.
