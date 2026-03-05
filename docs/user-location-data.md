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
