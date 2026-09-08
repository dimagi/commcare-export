# Changelog

## [1.16.0] - 2026-09-08

- Added Delta Lake as an output format
- Faster, lower-memory SQL exports via batched upserts
- Upgraded to SQLAlchemy 2.0
- Dropped support for Python 3.9; added support for Python 3.14

[1.16.0]: https://github.com/dimagi/commcare-export/compare/1.15.0...1.16.0

## [1.15.0] - 2026-01-27

- Alembic migrations are included in the package
- `AGENTS.md` and coding style documentation added

[1.15.0]: https://github.com/dimagi/commcare-export/compare/1.14.0...1.15.0

## [1.14.0] - 2026-01-09

- Faster exports (thanks to @jbinary)
- Reduced RAM use when exporting to CSV (thanks to @jbinary)
- Improved logging
- Switched to `pyproject.toml` + `uv`
- Extended type checking
- Dependency upgrades

[1.14.0]: https://github.com/dimagi/commcare-export/compare/1.13.0...1.14.0

## [1.13.0] - 2024-04-12

- A Windows-compatible executable file is compiled of the DET on every
  new release. It can be downloaded from the `Assets` section of the
  latest [release on GitHub](https://github.com/dimagi/commcare-export/releases)

[1.13.0]: https://github.com/dimagi/commcare-export/compare/1.12.0...1.13.0

## [1.12.0] - 2024-04-08

- Added a sample schedule script and updated the README on how to
  schedule runs
- Improved DET errors

[1.12.0]: https://github.com/dimagi/commcare-export/compare/1.11.0...1.12.0

## [1.11.0] - 2024-03-27

- The DET now logs progress and errors to a log file, unless the
  `no-logfile` option is specified, in which case all output is written
  to the terminal
- On every release an executable file is compiled of the DET and added
  as a release asset (currently Linux only)
- Various fixes and patches

[1.11.0]: https://github.com/dimagi/commcare-export/compare/1.10.2...1.11.0

## [1.10.2] - 2024-02-12

- Expanded on Python and virtualenv installation steps
- Only show detailed exception output when needed

[1.10.2]: https://github.com/dimagi/commcare-export/compare/1.10.1...1.10.2

## [1.10.1] - 2023-12-08

- Require `backoff` version >= 2.0.0, resolving an error
  (`module 'backoff' has no attribute 'runtime'`) when using
  `backoff` < 2.0.0 with v1.10.0

[1.10.1]: https://github.com/dimagi/commcare-export/compare/1.10.0...1.10.1

## [1.10.0] - 2023-10-31

- Rate-limited requests to CommCare HQ now wait for the amount of time
  specified by the `Retry-After` header instead of using exponential
  backoff
- Added checkpoint support for datasource exports
- Small fix in the code

[1.10.0]: https://github.com/dimagi/commcare-export/compare/1.9.0...1.10.0

## [1.9.0] - 2023-09-05

- Added support for CommCare UCR data source resource query files
- Added a test sequence to the GitHub workflow
- Small fixes in the code

[1.9.0]: https://github.com/dimagi/commcare-export/compare/1.8.1...1.9.0

## [1.8.1] - 2022-05-02

- For SQL exports, dropped the need to read the metadata of the
  destination database; use the metadata of the destination table
  instead
- Small fix and documentation update

[1.8.1]: https://github.com/dimagi/commcare-export/compare/1.8.0...1.8.1

## [1.8.0] - 2022-05-02

- Fixed support for Alembic >= 1.7
- Dropped libraries required by Python 2
- Cleaned up code and applied a code formatter
- Added mypy config for type checking

[1.8.0]: https://github.com/dimagi/commcare-export/compare/1.7.4...1.8.0

## [1.7.4] - 2021-11-10

- Prompt for username & password before they are needed
- Changed location of the MSSQL docker image
- Added optional dependencies

[1.7.4]: https://github.com/dimagi/commcare-export/compare/1.7.3...1.7.4

## [1.7.3] - 2021-07-15

- Added `unique` function for removing duplicates from list output

[1.7.3]: https://github.com/dimagi/commcare-export/releases/tag/1.7.3

## [1.7.2] - 2021-07-07

- Use `date_last_activity` for filtering / ordering of messaging data

[1.7.2]: https://github.com/dimagi/commcare-export/releases/tag/1.7.2

## [1.7.1] - 2021-06-30

- Switched from `jsonpath-rw` to `jsonpath-ng`

[1.7.1]: https://github.com/dimagi/commcare-export/releases/tag/1.7.1

## [1.7.0] - 2021-06-30

- Added an option to export the root document if no sub-document
  exists, via the `--export-root-if-no-subdocument` command line
  argument. When the root document expression of an export refers to a
  sub-document or list of sub-documents, all source expressions are
  evaluated against the sub-document unless prefixed with `$.`, in
  which case they refer to the root document. With this option, rows
  are exported even if the sub-document does not exist; only root
  document expressions (prefixed with `$.`) are evaluated, and all
  others yield a blank value

[1.7.0]: https://github.com/dimagi/commcare-export/releases/tag/1.7.0

## [1.6.2] - 2021-06-22

- Fixed `KeyError` for the `messaging-events` API

[1.6.2]: https://github.com/dimagi/commcare-export/releases/tag/1.6.2

## [1.6.1] - 2021-06-17

- More verbose error logging when the `--verbose` flag is used
- Updated messaging events pagination parameters to support an API
  update

[1.6.1]: https://github.com/dimagi/commcare-export/releases/tag/1.6.1

## [1.6.0] - 2021-03-16

- Added support for saving JSON data to Postgres databases
- Added the ability to export messaging events

[1.6.0]: https://github.com/dimagi/commcare-export/releases/tag/v1.6.0

## [1.5.0] - 2021-02-02

### Changed

- Introduced a new pagination mode for form and case exports to SQL
  databases, to avoid edge cases where data may be missed. Previously,
  the modification dates of forms and cases (`server_modified_on` for
  forms, `server_date_modified` for cases) were used for sorting and
  pagination. From this version, the default is to use the
  `indexed_on` field instead. The new mode is used automatically for
  new tables, and for runs using `--since` or `--start-over`; existing
  tables continue with the old mode until re-synced. It is recommended
  that all existing tables be re-synced using `--start-over`

### Added

- Added "data source" and "last_doc_id" to checkpoints
- Added a test that emitted rows is a generator

[1.5.0]: https://github.com/dimagi/commcare-export/releases/tag/v1.5.0

## [1.4.0] - 2020-12-11

### Fixed

- Fixed data not being written until the end of the last batch
  (regression introduced in 1.3.0); this bug could result in data not
  being written to the SQL database if an error occurred mid-batch,
  even though the checkpoint would still advance

### Added

- Added `form_url` and `case_url` Map Via functions
- Added a `format-uuid` function to format UUID hashes

### Changed

- Use `nvarchar` with fixed length in MSSQL to allow indexing
- Removed whitespace from the beginning and end of column names
- Added support for Python 3.8

[1.4.0]: https://github.com/dimagi/commcare-export/releases/tag/v.1.4.0

## [1.3.3] - 2020-06-26

- Fixed a bug where an error occurred after exporting 11 batches of
  data
- Improved data type support

[1.3.3]: https://github.com/dimagi/commcare-export/releases/tag/1.3.3

## [1.3.2] - 2020-06-19

- Fixed a bug with the markdown output format

[1.3.2]: https://github.com/dimagi/commcare-export/releases/tag/1.3.2

## [1.3.1] - 2020-06-04

- Increased the default `--batch-size` to `200`. The previous value of
  `100` could cause the tool to loop forever if more than 100 objects
  shared the same timestamp

[1.3.1]: https://github.com/dimagi/commcare-export/releases/tag/1.3.1

## [1.3.0] - 2020-06-03

- Added the `--with-organization` flag, providing a simple way to
  export location data and join it with forms and cases
- Added support for a "Data Type" column in Excel query files, allowing
  the SQL data type of a column to be set explicitly. Columns with an
  explicit data type are created immediately, instead of on first data

[1.3.0]: https://github.com/dimagi/commcare-export/releases/tag/1.3.0

## [1.2.4] - 2020-05-19

- Changed the Oracle text column from CLOB to VARCHAR2

[1.2.4]: https://github.com/dimagi/commcare-export/releases/tag/1.2.4

## [1.2.3] - 2020-05-17

- Added support for exporting locations
- Added support for exporting users
- Added experimental support for Oracle databases

[1.2.3]: https://github.com/dimagi/commcare-export/releases/tag/1.2.3

## [1.2.2] - 2020-05-17

- Added support for backing off on 429 rate-limiting responses

[1.2.2]: https://github.com/dimagi/commcare-export/releases/tag/1.2.2

## [1.2.1] - 2019-08-23

- Improved type checks when using `--strict-types`
- Fixed a type error when using mappings

[1.2.1]: https://github.com/dimagi/commcare-export/releases/tag/1.2.1

## [1.2.0] - 2019-07-10

### Added

- Added a `sha1` function to allow creating hashes of output values,
  useful when exporting nested objects where the jsonpath ID becomes
  too long for the SQL primary key column

### Fixed

- Stopped setting the checkpoint to the current time; always use the
  time from the batch if available, otherwise don't log a checkpoint
- Use a separate checkpoint for each table being exported (affects
  export configurations with multiple tables in one file)

### Changed

- Improved console logging
- Fixed deprecation warnings

**Upgrade notes:** if exporting to SQL with config files that have
multiple tables (Excel sheets), it is recommended to do a full
re-export using `--start-over`, by editing the file to change the
checkpoint key, or via `commcare-export-utils set-checkpoint-key`.

[1.2.0]: https://github.com/dimagi/commcare-export/releases/tag/1.2.0

## [1.1.1] - 2019-02-05

- Upgraded `openpyxl`

[1.1.1]: https://github.com/dimagi/commcare-export/releases/tag/1.1.1

## [1.1.0] - 2018-12-24

- For string columns, use `NVARCHAR(MAX)` in MSSQL and `TEXT` in
  PostgreSQL

[1.1.0]: https://github.com/dimagi/commcare-export/releases/tag/v1.1.0

## [1.0.2] - 2018-10-11

- Catch all parsing errors from jsonpath

[1.0.2]: https://github.com/dimagi/commcare-export/releases/tag/1.0.2

## [1.0.1] - 2018-10-08

- Correctly handle unicode characters in headings when writing data to
  CSV

[1.0.1]: https://github.com/dimagi/commcare-export/releases/tag/1.0.1

## [1.0.0] - 2018-09-04

- Improved performance when exporting multiple tables from the same
  datasource (e.g. form + repeats): data is now fetched once and each
  table processes it directly, instead of re-fetching for each table
- Added support for specifying alternate source field names: each
  source field is considered in order and the first one present in the
  data is used. Alternates can be listed as CSV in an "Alternate Source
  Fields" column, or in individual "Alternate Source Field [N]" columns
- Added support for specifying a checkpoint key via the command line,
  to avoid re-starting an export after editing the query file; added a
  `commcare-export-utils` tool for interrogating checkpoint data and
  converting non-keyed checkpoints to keyed checkpoints
- Stopped reusing checkpoints when querying different sources
- Added handling of errors encountered when fetching data, with retry
  and backoff
- Unwrap `object` values from CommCare HQ where possible
- Prevented `--since` and `--until` from affecting checkpoints
- Quote special characters in source field names
- Allowed specifying the SQL table name in the query sheet in addition
  to the sheet name, to work around limits on sheet name length

[1.0.0]: https://github.com/dimagi/commcare-export/releases/tag/1.0.0

## [0.22.3] - 2018-07-12

- Fixed a pagination bug for forms with multiple sorting

[0.22.3]: https://github.com/dimagi/commcare-export/releases/tag/0.22.3

## [0.22.1] - 2018-07-02

- Fixed a bug in checkpointing when exporting to SQL

[0.22.1]: https://github.com/dimagi/commcare-export/releases/tag/0.22.1

## [0.22.0] - 2018-05-31

- Added validation of field length when exporting to SQL, restricted
  to database maximums: 63 chars for PostgreSQL, 64 chars for MySQL,
  128 chars for MSSQL

[0.22.0]: https://github.com/dimagi/commcare-export/releases/tag/0.22.0

## [0.21.3] - 2018-05-30

- Prevented logging configuration from being overridden by the
  migration framework

[0.21.3]: https://github.com/dimagi/commcare-export/releases/tag/0.21.3

## [0.21.2] - 2018-05-17

- Fixed a packaging issue causing migrations not to be installed

[0.21.2]: https://github.com/dimagi/commcare-export/releases/tag/0.21.2

## [0.21.1] - 2018-05-15

- Fixed a missing version file from the 0.21.0 release (broken package)
- Fixed `str2num` for blank fields

[0.21.1]: https://github.com/dimagi/commcare-export/releases/tag/0.21.1

## [0.21.0] - 2018-05-08

- Added official support for MS SQL Server using `pyodbc` (broken
  package, fixed in 0.21.1)

[0.21.0]: https://github.com/dimagi/commcare-export/releases/tag/0.21.0

## [0.20.2] - 2018-05-04

- Added a missing VERSION file to the build

[0.20.2]: https://github.com/dimagi/commcare-export/releases/tag/0.20.2

## [0.20.1] - 2018-05-04

- Added support for API key authentication (broken package, fixed in
  0.20.2)

[0.20.1]: https://github.com/dimagi/commcare-export/releases/tag/0.20.1

## [0.19.1] - 2018-01-25

- Fixed an issue with missing DB migration resources

[0.19.1]: https://github.com/dimagi/commcare-export/releases/tag/0.19.1

## [0.19.0] - 2018-01-22

- Use the migrations framework for maintaining the checkpoint table
- Allowed changing VARCHAR column length or to TEXT type when in
  "strict types" mode

[0.19.0]: https://github.com/dimagi/commcare-export/releases/tag/0.19.0

## [0.18.1] - 2017-12-08

- Fixed a bug in checkpointing that was using an incorrect date

[0.18.1]: https://github.com/dimagi/commcare-export/releases/tag/0.18.1

## [0.18.0] - 2017-12-04

- Allowed function arguments to contain `()` characters

[0.18.0]: https://github.com/dimagi/commcare-export/releases/tag/0.18.0

## [0.17.0] - 2017-11-23

- Always use the current version during build
- Fail on unicode args
- Stopped writing missing values to Excel as an empty string

[0.17.0]: https://github.com/dimagi/commcare-export/releases/tag/0.17.0

## [0.16.0] - 2017-09-20

- Clearer exception message for execution failures
- Filter forms by `server_modifed_on` or `received_on`
- Treat empty lists as a missing value

[0.16.0]: https://github.com/dimagi/commcare-export/releases/tag/0.16.0

## [0.15.2] - 2017-09-05

- Actually use `NULL` as the missing value

[0.15.2]: https://github.com/dimagi/commcare-export/releases/tag/0.15.2

## [0.15.1] - 2017-09-05

- Added a warning for bad sheets
- Default missing-value to `NULL` for SQL

[0.15.1]: https://github.com/dimagi/commcare-export/releases/tag/0.15.1

## [0.15.0] - 2017-09-05

- Refactored checkpointing

[0.15.0]: https://github.com/dimagi/commcare-export/releases/tag/0.15.0

## [0.14.0] - 2017-08-07

- Fixed Python 3 support
- Checkpoint more frequently when exporting to SQL, to allow for
  easier recovery after failure

[0.14.0]: https://github.com/dimagi/commcare-export/releases/tag/0.14.0

## [0.13.3] - 2017-08-02

[0.13.3]: https://github.com/dimagi/commcare-export/releases/tag/0.13.3

## [0.13.2] - 2017-07-12

- Added `template` Map Via function
- Added `attachment_url` Map Via function

[0.13.2]: https://github.com/dimagi/commcare-export/releases/tag/0.13.2

## [0.13.1] - 2017-07-04

- Implemented date-based pagination of forms and cases to avoid deep
  pagination slowdown on large exports

[0.13.1]: https://github.com/dimagi/commcare-export/releases/tag/0.13.1

## [0.12.9] - 2017-06-26

- Safer unicode conversion
- Handle empty string correctly in `str2bool`
- Better support for MySQL booleans

[0.12.9]: https://github.com/dimagi/commcare-export/releases/tag/0.12.9

## [0.12.8] - 2017-05-23

- Fixed unicode handling in Map Via functions

[0.12.8]: https://github.com/dimagi/commcare-export/releases/tag/v0.12.8

## [0.12.7] - 2016-12-12

[0.12.7]: https://github.com/dimagi/commcare-export/releases/tag/0.12.7

## [0.12.6] - 2016-12-12

[0.12.6]: https://github.com/dimagi/commcare-export/releases/tag/0.12.6

## [0.12.5] - 2016-12-12

[0.12.5]: https://github.com/dimagi/commcare-export/releases/tag/0.12.5

## [0.12.4] - 2016-12-12

[0.12.4]: https://github.com/dimagi/commcare-export/releases/tag/0.12.4

## [0.12.3] - 2016-12-12

[0.12.3]: https://github.com/dimagi/commcare-export/releases/tag/0.12.3

## [0.12.2] - 2015-07-13

- Don't attempt to alter a column that is already of type TEXT
- Make headings in the Excel config file case-insensitive
- Added a `--version` option to the CLI

[0.12.2]: https://github.com/dimagi/commcare-export/releases/tag/0.12.2

## [0.12.0] - 2015-06-30

- Added better support for types, especially dates
- Don't create columns until the type is known
- Added a `strict-types` option to prevent changing column types

[0.12.0]: https://github.com/dimagi/commcare-export/releases/tag/0.12.0

## [0.11.8] - 2015-03-09

- Made `digest` the default authentication mode
- Refactored form filters to stop using the `_search` backdoor

[0.11.8]: https://github.com/dimagi/commcare-export/releases/tag/0.11.8

## [0.11.7] - 2014-07-08

- Added support for `openpyxl` >= 2.0.0

[0.11.7]: https://github.com/dimagi/commcare-export/releases/tag/0.11.7

## [0.11.6] - 2014-04-10

- Added support for the `bool` operator in "Map Via" or "Format Via"
- Added digest authentication mode via the `--auth-mode` option
  (accepted values are `session` and `digest`)
- Added support for descendant expressions as a data source, e.g.
  `form[*]..form.case`

[0.11.6]: https://github.com/dimagi/commcare-export/releases/tag/0.11.6
