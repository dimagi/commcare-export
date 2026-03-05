MiniLinq Reference
------------------

The abstract syntax can be directly inspected in the `commcare_export.minilinq` module. Note that the choice between functions and primitives is deliberately chosen
to expose the structure of the MiniLinq for possible optimization, and to restrict the overall language.

Here is a description of the astract syntax and semantics

| Python                        | JSON                                                | Which is evaluates to            |
|-------------------------------|-----------------------------------------------------|----------------------------------|
| `Literal(v)`                  | `{"Lit": v}`                                        | Just `v`                         |
| `Reference(x)`                | `{"Ref": x}`                                        | Whatever `x` resolves to in the environment |
| `List([a, b, c, ...])`        | `{"List": [a, b, c, ...}`                           | The list of what `a`, `b`, `c` evaluate to |
| `Map(source, name, body)`     | `{"Map": {"source": ..., "name": ..., "body": ...}` | Evals `body` for each elem in `source`. If `name` is provided, the elem will be bound to it, otherwise it will replace the whole env. |
| `FlatMap(source, name, body)` | `{"FlatMap": {"source" ... etc}}` | Flattens after mapping, like nested list comprehensions |
| `Filter(source, name, body)`  | etc | |
| `Bind(value, name, body)`     | etc | Binds the result of `value` to `name` when evaluating `body` |
| `Emit(table, headings, rows)` | etc | Emits `table` with `headings` and `rows`. Note that `table` is a string, `headings` is a list of expressions, and `rows` is a list of lists of expressions. See explanation below for emitted output. |
| `Apply(fn, args)` | etc | Evaluates `fn` to a function, and all of `args`, then applies the function to the args. |

Built in functions like `api_data` and basic arithmetic and comparison are provided via the environment,
referred to be name using `Ref`, and utilized via `Apply`.

List of builtin functions:

| Function                       | Description                                                                    | Example Usage                    |
|--------------------------------|--------------------------------------------------------------------------------|----------------------------------|
| `+, -, *, //, /, >, <, >=, <=` | Standard Math                                                                  |                                  |
| len                            | Length                                                                         |                                  |
| bool                           | Bool                                                                           |                                  |
| str2bool                       | Convert string to boolean. True values are 'true', 't', '1' (case insensitive) |                                  |
| str2date                       | Convert string to date                                                         |                                  |
| bool2int                       | Convert boolean to integer (0, 1)                                              |                                  |
| str2num                        | Parse string as a number                                                       |                                  |
| format-uuid                    | Parse a hex UUID, and format it into hyphen-separated groups                   |                                  |
| substr                         | Returns substring indexed by [first arg, second arg), zero-indexed.            | substr(2, 5) of 'abcdef' = 'cde' |
| selected-at                    | Returns the Nth word in a string. N is zero-indexed.                           | selected-at(3) - return 4th word |
| selected                       | Returns True if the given word is in the value.                                | selected(fever)                  |
| count-selected                 | Count the number of words                                                      |                                  |
| json2str                       | Convert a JSON object to a string                                              |                                  |
| template                       | Render a string template (not robust)                                          | template({} on {}, state, date)  |
| attachment_url                 | Convert an attachment name into it's download URL                              |                                  |
| form_url                       | Output the URL to the form view on CommCare HQ                                 |                                  |
| case_url                       | Output the URL to the case view on CommCare HQ                                 |                                  |
| unique                         | Ouptut only unique values in a list                                            |                                  |
