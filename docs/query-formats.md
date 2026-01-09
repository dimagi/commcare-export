Query Formats
=============

*Part of [Technical Documentation](index.md)*

CommCare Export supports two query formats: Excel and JSON. Both formats
are compiled to [MiniLinq](minilinq-reference.md) for execution.


Excel Query Format
------------------

An Excel query is any `.xlsx` workbook. Each sheet in the workbook
represents one table you wish to create. This format is recommended as
it's more user-friendly and stable across library versions.

### Structure

There are several column groupings to configure each table:

| Column Group                       | Description                                                                            |
|------------------------------------|----------------------------------------------------------------------------------------|
| **Data Source**                    | Set this to `form` to export form data, or `case` for case data                        |
| **Filter Name** / **Filter Value** | These columns are paired up to filter the input cases or forms                         |
| **Field**                          | The destination column name in your output table                                       |
| **Source Field**                   | The particular field from the form/case you wish to extract. This can be any JSON path |

### Column Details

#### Data Source Column

- **Values**: `form` or `case`
- **Purpose**: Specifies whether to query form submissions or cases
- **Required**: Yes, one per sheet

#### Filter Name / Filter Value Pairs

These columns work together to filter the data retrieved from CommCare HQ:

- **Filter Name**: The name of the filter (e.g., `xmlns`, `app_id`,
  `case_type`)
- **Filter Value**: The value to filter by
- **Multiple Filters**: You can have multiple filter pairs in the same
  sheet

**Common Filter Examples:**

| Filter Name | Filter Value                           | Description                 |
|-------------|----------------------------------------|-----------------------------|
| `xmlns`     | `http://openrosa.org/formdesigner/...` | Filter forms by XMLNS       |
| `app_id`    | Your app ID                            | Filter forms by application |
| `case_type` | `patient`                              | Filter cases by type        |

**Finding Form XMLNS:**

To determine the XMLNS for your form, see
[Finding a Form's XMLNS](https://confluence.dimagi.com/display/commcarepublic/Finding+a+Form%27s+XMLNS).

#### Field Column

- **Purpose**: The name of the column in your output table
- **Format**: Any valid column name (avoid special characters)
- **Example**: `patient_name`, `visit_date`, `form_id`

#### Source Field Column

- **Purpose**: The JSON path to extract data from the form or case
- **Format**: JSON path notation (dot-separated)
- **Examples**:
  - `form.patient_name` - Extract patient_name from form
  - `received_on` - Extract the received_on timestamp
  - `form.visit.symptoms.fever` - Extract nested fields
  - `case_id` - Extract the case ID

**JSON Path Support:**

The Source Field supports full JSON path notation, allowing you to:
- Access nested objects: `form.patient.name.first`
- Access array elements: `form.children[0].name`
- Use wildcards: `form.*.value`

### Example Excel Query

Here's what a simple Excel query sheet might look like:

| Data Source | Filter Name | Filter Value                         | Field             | Source Field      |
|-------------|-------------|--------------------------------------|-------------------|-------------------|
| form        | xmlns       | http://openrosa.org/.../registration |                   |                   |
|             |             |                                      | Patient ID        | form.patient_id   |
|             |             |                                      | Patient Name      | form.patient_name |
|             |             |                                      | Registration Date | received_on       |
|             |             |                                      | Visit Type        | form.visit_type   |

This query would:
1. Export form data
2. Filter to forms with the specified XMLNS
3. Create a table with 4 columns: Patient ID, Patient Name, Registration
   Date, and Visit Type

### Multiple Sheets

Each sheet in the Excel workbook creates a separate output table. The
sheet name becomes the table name (for SQL outputs) or sheet name
(for Excel outputs).

**Example workbook structure:**

- Sheet: `patient_registrations` - Export registration forms
- Sheet: `patient_visits` - Export visit forms
- Sheet: `patient_cases` - Export patient cases

### Best Practices

1. **Use Descriptive Sheet Names**: These become your table names
2. **Keep Column Names Simple**: Avoid spaces and special characters in
   Field columns
3. **Filter Appropriately**: Use filters to limit data and improve
   performance
4. **Test with Small Data**: Use date filters (via command-line) when
   testing
5. **Document Your Queries**: Add comments in unused columns to explain
   complex logic


JSON Query Format
-----------------

JSON queries provide a more direct representation of
[MiniLinq](minilinq-reference.md) queries. They offer more flexibility
but are less user-friendly than Excel.

### Structure

A JSON query is a MiniLinq expression serialized as JSON. See the
[MiniLinq Reference](minilinq-reference.md) for complete syntax.

### Converting Excel to JSON

The best way to understand JSON queries is to create an Excel query and
convert it:

```shell
commcare-export --query my-query.xlsx --dump-query
```

This will output the compiled MiniLinq JSON without executing the query.

### Example JSON Query

Here's a simple JSON query equivalent to the Excel example above:

```json
{
  "Emit": {
    "table": "patient_registrations",
    "headings": [
      {"Lit": "Patient ID"},
      {"Lit": "Patient Name"},
      {"Lit": "Registration Date"},
      {"Lit": "Visit Type"}
    ],
    "source": {
      "Map": {
        "source": {
          "Apply": {
            "fn": {"Ref": "api_data"},
            "args": [
              {"Lit": "form"},
              {"Lit": {
                "filter": {
                  "term": {
                    "xmlns": "http://openrosa.org/.../registration"
                  }
                }
              }}
            ]
          }
        },
        "body": {
          "List": [
            {"Ref": "form.patient_id"},
            {"Ref": "form.patient_name"},
            {"Ref": "received_on"},
            {"Ref": "form.visit_type"}
          ]
        }
      }
    }
  }
}
```

### When to Use JSON

Use JSON queries when you need:

- Programmatic query generation
- Complex transformations not expressible in Excel
- Custom filtering logic
- Dynamic queries based on runtime conditions
- Version control friendly format (though Excel works too)

### When to Use Excel

Use Excel queries when you want:

- User-friendly query creation
- Visual organization of multiple tables
- Quick prototyping and iteration
- Stable format across library versions (recommended)
- Easy sharing with non-technical users


Examples
--------

The `examples/` directory contains sample queries in both formats:

**Excel Examples:**
- `examples/demo-registrations.xlsx`
- `examples/demo-pregnancy-cases.xlsx`
- `examples/demo-pregnancy-cases-with-forms.xlsx`
- `examples/demo-deliveries.xlsx`
- `examples/generic-form-metadata.xlsx`

**JSON Examples:**
- `examples/demo-registrations.json`
- `examples/demo-pregnancy-cases.json`
- `examples/demo-pregnancy-cases-with-forms.json`
- `examples/demo-deliveries.json`

All examples are based on the CommCare Demo App available on the
CommCare HQ Exchange.


Troubleshooting
---------------

### Issue: No data returned

**Solutions:**
- Verify your Filter Value matches exactly (case-sensitive)
- Check that data exists in the date range you're querying
- Use `--output-format markdown` to see if any data is being retrieved
- Test without filters first to ensure the data source is correct

### Issue: Wrong data in columns

**Solutions:**
- Verify Source Field JSON paths are correct
- Use CommCare HQ's Export Tool to see raw data structure
- Check for typos in field names (they're case-sensitive)
- Test with `--dump-query` to see the compiled query

### Issue: Excel workbook not recognized

**Solutions:**
- Ensure file has `.xlsx` extension (not `.xls`)
- Verify file is not corrupted
- Check that all required columns are present
- Make sure Data Source is set to `form` or `case`


See Also
--------

- [MiniLinq Reference](minilinq-reference.md) - Query language
  documentation
- [Output Formats](output-formats.md) - Available output formats
- [Python Library Usage](library-usage.md) - Using queries from Python
  code
- [Examples Directory](../examples/) - Sample queries
