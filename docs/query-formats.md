Query Formats
=============

The Data Export Tool supports two query formats: Excel and JSON. Both
are compiled to [MiniLinq](minilinq-reference.md) for execution.

For detailed guidance on creating queries, including field mappings,
filter examples, and tips, see the
[User Documentation](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955952/CommCare+Data+Export+Tool+DET#Creating-an-Excel-Query-File-in-CommCare-HQ).


Excel Queries
-------------

An Excel query is any `.xlsx` workbook. Each sheet represents one output
table. Columns are grouped as follows:

- **Data Source**: `form` for form data, or `case` for case data
- **Filter Name** / **Filter Value**: Paired columns to filter the data
- **Field**: The destination column name in your output
- **Source Field**: The JSON path to extract from the form or case

It is recommended to use the Excel format as it is more user-friendly
and stable across library versions.


JSON Queries
------------

JSON queries represent [MiniLinq](minilinq-reference.md) expressions
directly. To get started with JSON, create an Excel query and convert
it:

```shell
commcare-export --query my-query.xlsx --dump-query
```


Examples
--------

Example query files in both formats are provided in the
[examples/](../examples/) directory. They work with the CommCare Demo
App available on the CommCare HQ Exchange.


See Also
--------

- [MiniLinq Reference](minilinq-reference.md) - Query language
  documentation
- [Output Formats](output-formats.md) - Available output formats
