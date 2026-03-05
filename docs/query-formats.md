Excel Queries
-------------

An Excel query is any `.xlsx` workbook. Each sheet in the workbook represents one table you wish
to create. There are two grouping of columns to configure the table:

 - **Data Source**: Set this to `form` to export form data, or `case` for case data.
 - **Filter Name** / *Filter Value*: These columns are paired up to filter the input cases or forms.
 - **Field**: The destination in your SQL database for the value.
 - **Source Field**: The particular field from the form you wish to extract. This can be any JSON path.


JSON Queries
------------

JSON queries are a described in the table below. You build a JSON object that represents the query you have in mind.
A good way to get started is to work from the examples, or you could make an Excel query and run the tool
with `--dump-query` to see the resulting JSON query.
