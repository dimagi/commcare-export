MiniLinq Reference
==================

*Part of [Technical Documentation](index.md)*

MiniLinq is a simple query language for extracting and transforming data
from CommCare HQ. It can be expressed in both Python (for library
users) and JSON (for serialization and Excel compilation).

The abstract syntax can be directly inspected in the
`commcare_export.minilinq` module. Note that the choice between
functions and primitives is deliberately chosen to expose the structure
of the MiniLinq for possible optimization, and to restrict the overall
language.


Abstract Syntax
---------------

Here is a description of the abstract syntax and semantics:

| Python                        | JSON                                                     | Evaluates to                                                     |
|-------------------------------|----------------------------------------------------------|------------------------------------------------------------------|
| `Literal(v)`                  | `{"Lit": v}`                                             | Just `v`                                                         |
| `Reference(x)`                | `{"Ref": x}`                                             | Whatever `x` resolves to in the environment                      |
| `List([a, b, c, ...])`        | `{"List": [a, b, c, ...]}`                               | The list of what `a`, `b`, `c` evaluate to                       |
| `Map(source, name, body)`     | `{"Map": {"source": ..., "name": ..., "body": ...}}`     | Evals `body` for each elem in `source`. If `name` is provided, the elem will be bound to it, otherwise it will replace the whole env. |
| `FlatMap(source, name, body)` | `{"FlatMap": {"source": ..., "name": ..., "body": ...}}` | Flattens after mapping, like nested list comprehensions          |
| `Filter(source, name, body)`  | `{"Filter": {"source": ..., "name": ..., "body": ...}}`  | Filters `source` keeping elements where `body` evaluates to true |
| `Bind(value, name, body)`     | `{"Bind": {"value": ..., "name": ..., "body": ...}}`     | Binds the result of `value` to `name` when evaluating `body`     |
| `Emit(table, headings, rows)` | `{"Emit": {"table": ..., "headings": ..., "rows": ...}}` | Emits `table` with `headings` and `rows`. Note that `table` is a string, `headings` is a list of expressions, and `rows` is a list of lists of expressions. See [Output Formats](output-formats.md) for emitted output. |
| `Apply(fn, args)`             | `{"Apply": {"fn": ..., "args": [...]}}`                  | Evaluates `fn` to a function, and all of `args`, then applies the function to the args. |


Examples
--------

### Basic Reference and Literal

```python
# Reference a field from the current environment
Reference("form.name")  # JSON: {"Ref": "form.name"}

# Literal value
Literal("Hello")  # JSON: {"Lit": "Hello"}
```

### List Construction

```python
# Create a list of expressions
List([
    Reference("form.name"),
    Reference("form.age"),
    Reference("form.gender")
])
```

### Map Operation

```python
# Map over a list of forms, extracting specific fields
Map(
    source=Apply(Reference("api_data"), Literal("form")),
    name="form",
    body=List([
        Reference("form.id"),
        Reference("form.name")
    ])
)
```

### Filter Operation

```python
# Filter forms where form.completed is true
Filter(
    source=Apply(Reference("api_data"), Literal("form")),
    name="form",
    body=Apply(
        Reference("="),
        [Reference("form.completed"), Literal("true")]
    )
)
```

### Emit for Output

```python
# Create a table output
Emit(
    'patient_data',
    [
        Literal('Patient ID'),
        Literal('Name'),
        Literal('Age')
    ],
    Map(
        source=Apply(Reference("api_data"), Literal("form")),
        name="form",
        body=List([
            Reference("form.patient_id"),
            Reference("form.patient_name"),
            Reference("form.patient_age")
        ])
    )
)
```


Built-in Functions
------------------

Built-in functions like `api_data` and basic arithmetic and comparison
are provided via the environment, referred to by name using `Ref`, and
utilized via `Apply`.

### Arithmetic and Comparison

| Function         | Description                    |
|------------------|--------------------------------|
| `+, -, *, //, /` | Standard arithmetic operations |
| `>, <, >=, <=`   | Comparison operators           |

### Type Conversions

| Function   | Description                       | Example Usage                                   |
|------------|-----------------------------------|-------------------------------------------------|
| `len`      | Length of a string or list        | `Apply(Reference("len"), [Reference("field")])` |
| `bool`     | Convert to boolean                |                                                 |
| `str2bool` | Convert string to boolean. True values are 'true', 't', '1' (case insensitive) |    |
| `str2date` | Convert string to date            |                                                 |
| `bool2int` | Convert boolean to integer (0, 1) |                                                 |
| `str2num`  | Parse string as a number          |                                                 |

### String Operations

| Function      | Description                                                  | Example Usage                       |
|---------------|--------------------------------------------------------------|-------------------------------------|
| `substr`      | Returns substring indexed by [first arg, second arg), zero-indexed | `substr(2, 5)` of 'abcdef' = 'cde' |
| `template`    | Render a string template (not robust)                        | `template("{} on {}", state, date)` |
| `format-uuid` | Parse a hex UUID, and format it into hyphen-separated groups |                                     |
| `json2str`    | Convert a JSON object to a string                            |                                     |

### Multi-select Operations

These functions are useful for working with CommCare multi-select
questions:

| Function         | Description                                         | Example Usage                      |
|------------------|-----------------------------------------------------|------------------------------------|
| `selected-at`    | Returns the Nth word in a string. N is zero-indexed | `selected-at(3)` - return 4th word |
| `selected`       | Returns True if the given word is in the value      | `selected("fever")`                |
| `count-selected` | Count the number of words                           |                                    |

### CommCare-specific Functions

| Function         | Description                                      |
|------------------|--------------------------------------------------|
| `attachment_url` | Convert an attachment name into its download URL |
| `form_url`       | Output the URL to the form view on CommCare HQ   |
| `case_url`       | Output the URL to the case view on CommCare HQ   |

### List Operations

| Function | Description                         |
|----------|-------------------------------------|
| `unique` | Output only unique values in a list |


Environment Concepts
--------------------

MiniLinq queries are evaluated in an environment that provides:

1. **Built-in Functions**: Math, string operations, type conversions
   (provided by `BuiltInEnv`)

2. **Data Access**: The `api_data` function for fetching from CommCare
   HQ (provided by `CommCareHqEnv`)

3. **JSON Path Navigation**: Access to nested data structures
   (provided by `JsonPathEnv`)

Environments are composed using the `|` operator:

```python
env = BuiltInEnv() | CommCareHqEnv(api_client) | JsonPathEnv()
```


Converting Excel to JSON
------------------------

If you have an Excel query and want to see the corresponding MiniLinq
JSON, use the `--dump-query` option:

```shell
commcare-export --query my-query.xlsx --dump-query
```

This will output the compiled MiniLinq query in JSON format without
executing it.


Optimization Tips
-----------------

1. **Filter Early**: Apply filters as early as possible to reduce the
   amount of data processed

2. **Use Specific API Filters**: Leverage CommCare HQ's API filters
   (e.g., `date_modified`) rather than filtering in MiniLinq

3. **Minimize Nested Maps**: Deeply nested Map operations can be slow;
   consider restructuring if possible


Debugging Strategies
--------------------

1. **Use Markdown Output**: Start with `--output-format markdown` to see
   query results quickly

2. **Dump Query JSON**: Use `--dump-query` to inspect the compiled
   query

3. **Test with Small Date Ranges**: Use `--since` and `--until` to limit
   data while debugging

4. **Check API Responses**: Use the `--verbose` flag to see API requests
   and responses


See Also
--------

- [Python Library Usage](library-usage.md) - Using MiniLinq from Python
- [Query Formats](query-formats.md) - Excel and JSON query specifications
- [Examples](../examples/) - Example queries in both Excel and JSON formats
