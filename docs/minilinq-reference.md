MiniLinq Reference
==================

MiniLinq is a simple query language for extracting and transforming data
from CommCare HQ. It can be expressed in both Python (for library
users) and JSON (for serialization and Excel compilation).

The abstract syntax can be directly inspected in the
`commcare_export.minilinq` module. The choice between functions and
primitives is deliberately chosen to expose the structure of the MiniLinq
for possible optimization, and to restrict the overall language.


Abstract Syntax
---------------

| Python                        | JSON                                                     | Evaluates to                                                     |
|-------------------------------|----------------------------------------------------------|------------------------------------------------------------------|
| `Literal(v)`                  | `{"Lit": v}`                                             | Just `v`                                                         |
| `Reference(x)`                | `{"Ref": x}`                                             | Whatever `x` resolves to in the environment                      |
| `List([a, b, c, ...])`        | `{"List": [a, b, c, ...]}`                               | The list of what `a`, `b`, `c` evaluate to                       |
| `Map(source, name, body)`     | `{"Map": {"source": ..., "name": ..., "body": ...}}`     | Evals `body` for each elem in `source`. If `name` is provided, the elem will be bound to it, otherwise it will replace the whole env. |
| `FlatMap(source, name, body)` | `{"FlatMap": {"source": ..., "name": ..., "body": ...}}` | Flattens after mapping, like nested list comprehensions          |
| `Filter(source, name, body)`  | `{"Filter": {"source": ..., "name": ..., "body": ...}}`  | Filters `source` keeping elements where `body` evaluates to true |
| `Bind(value, name, body)`     | `{"Bind": {"value": ..., "name": ..., "body": ...}}`     | Binds the result of `value` to `name` when evaluating `body`     |
| `Emit(table, headings, rows)` | `{"Emit": {"table": ..., "headings": ..., "rows": ...}}` | Emits `table` with `headings` and `rows`. `table` is a string, `headings` is a list of expressions, and `rows` is a list of lists of expressions. See [Output Formats](output-formats.md). |
| `Apply(fn, args)`             | `{"Apply": {"fn": ..., "args": [...]}}`                  | Evaluates `fn` to a function, and all of `args`, then applies the function to the args. |


Built-in Functions
------------------

Built-in functions like `api_data` and basic arithmetic and comparison
are provided via the environment, referred to by name using `Ref`, and
utilized via `Apply`.

### Arithmetic and Comparison

| Function                       | Description    |
|--------------------------------|----------------|
| `+, -, *, //, /, >, <, >=, <=` | Standard math |

### Type Conversions

| Function   | Description                                                             |
|------------|-------------------------------------------------------------------------|
| `len`      | Length of a string or list                                              |
| `bool`     | Convert to boolean                                                      |
| `str2bool` | Convert string to boolean. True values are 'true', 't', '1' (case insensitive) |
| `str2date` | Convert string to date                                                  |
| `bool2int` | Convert boolean to integer (0, 1)                                       |
| `str2num`  | Parse string as a number                                                |

### String Operations

| Function      | Description                                                          | Example                             |
|---------------|----------------------------------------------------------------------|--------------------------------------|
| `substr`      | Returns substring indexed by [first arg, second arg), zero-indexed   | `substr(2, 5)` of 'abcdef' = 'cde'  |
| `template`    | Render a string template (not robust)                                | `template("{} on {}", state, date)`  |
| `format-uuid` | Parse a hex UUID, and format it into hyphen-separated groups         |                                      |
| `json2str`    | Convert a JSON object to a string                                    |                                      |

### Multi-select Operations

Useful for working with CommCare multi-select questions:

| Function         | Description                                         | Example                            |
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
| `unique`         | Output only unique values in a list              |


Converting Excel to JSON
-------------------------

To see the MiniLinq JSON generated from an Excel query, use the
`--dump-query` option:

```shell
commcare-export --query my-query.xlsx --dump-query
```


See Also
--------

- [Python Library Usage](library-usage.md) - Using MiniLinq from Python
- [Query Formats](query-formats.md) - Excel and JSON query
  specifications
