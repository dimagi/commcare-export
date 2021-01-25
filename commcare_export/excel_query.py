from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import re
from collections import defaultdict, namedtuple

from jsonpath_rw.lexer import JsonPathLexerError
from six.moves import xrange

from jsonpath_rw import jsonpath
from jsonpath_rw.parser import parse as parse_jsonpath

from commcare_export.exceptions import LongFieldsException, MissingColumnException, ReservedTableNameException
from commcare_export.map_format import compile_map_format_via
from commcare_export.minilinq import *

def take_while(pred, iterator):
    for v in iterator:
        if pred(v):
            yield v
        else:
            return

def drop_while(pred, iterator):
    for v in iterator:
        if not pred(v):
            yield v
            break

    for v in iterator:
        yield v

def without_empty_tail(cells):
    """
    Returns the prefix of a column that is not entirely empty.
    """
    return list(reversed(list(drop_while(lambda v: (not v) or (not v.value), reversed(cells)))))

def map_value(mappings_sheet, mapping_name, source_value):
    "From the mappings_sheet, replaces the source_value with appropriate output value"
    return source_value


def get_column_by_name(worksheet, column_name):
    # columns and rows are indexed from 1
    for col in xrange(1, worksheet.max_column + 1):
        value = worksheet.cell(row=1, column=col).value
        value = value.lower().strip() if value else value
        if column_name == value:
            return without_empty_tail([
                worksheet.cell(row=i, column=col) for i in xrange(2, worksheet.max_row + 1)
            ])


def get_columns_by_prefix(worksheet, column_prefix):
    # columns and rows are indexed from 1
    for col in xrange(1, worksheet.max_column + 1):
        value = worksheet.cell(row=1, column=col).value
        if value and value.lower().startswith(column_prefix):
            yield value, without_empty_tail([
                worksheet.cell(row=i, column=col) for i in xrange(2, worksheet.max_row + 1)
            ])


def compile_mappings(worksheet):
    mapping_names = get_column_by_name(worksheet, "mapping name")
    sources       = extended_to_len(len(mapping_names), get_column_by_name(worksheet, "source"))
    destinations  = extended_to_len(len(mapping_names), get_column_by_name(worksheet, "destination"))

    mappings = defaultdict(lambda: defaultdict(lambda: None))
    
    for mapping_name, source, dest in zip(mapping_names, sources, destinations):
        if mapping_name and source:
            mappings[mapping_name.value][source.value] = dest.value if dest else None

    return mappings

def compile_filters(worksheet, mappings=None):
    filter_names  = [cell.value for cell in get_column_by_name(worksheet, 'filter name') or []]

    if not filter_names:
        return []

    filter_values = extended_to_len(len(filter_names), [cell.value for cell in get_column_by_name(worksheet, 'filter value') or []])
    return zip(filter_names, filter_values)

def extended_to_len(desired_len, some_list, value=None):
    return [some_list[i] if i < len(some_list) else value
            for i in xrange(0, desired_len)]


def _get_safe_source_field(source_field):
    def _safe_node(node):
        try:
            parse_jsonpath(node)
        except Exception:
            # quote nodes with special characters
            return '"{}"'.format(node)
        else:
            return node

    try:
        parse_jsonpath(source_field)
    except Exception:
        source_field = '.'.join([
            _safe_node(node) if node else node
            for node in source_field.split('.')
        ])
        if source_field.endswith('.'):
            raise Exception("Blank node path: {}".format(source_field))

    return Reference(source_field)


def compile_field(field, source_field, alternate_source_fields=None, map_via=None, format_via=None, mappings=None):
    expr = _get_safe_source_field(source_field)

    if alternate_source_fields:
        expr = Apply(Reference('or'), expr, *[Reference(alt_field) for alt_field in alternate_source_fields])
    if map_via:
        expr = compile_map_format_via(expr, map_via)

    if format_via:
        expr = compile_map_format_via(expr, format_via)

    if mappings and field in mappings:
        expr = compile_mapped_field(mappings[field], expr)

    return expr


def compile_mapped_field(field_mappings, field_expression):
    # quote the ref in case it has special chars
    quoted_field = Apply(Reference('join'), Literal(''), Literal('"'), field_expression, Literal('"'))
    # produce the mapping reference i.e. 'mapping."X"'
    mapping_ref = Apply(Reference('join'), Literal('.'), Literal('mapping'), quoted_field)
    # apply the reference to the field mappings to get the final value
    mapped_value = FlatMap(source=Literal([field_mappings]), body=Reference(mapping_ref), name='mapping')
    return Apply(Reference('default'), mapped_value, field_expression)


def _get_alternate_source_fields_from_csv(worksheet, num_fields):
    def _clean_csv_field(field):
        if field and field.value:
            return [val.strip() for val in field.value.split(',')]

    alt_source_col = get_column_by_name(worksheet, 'alternate source fields')

    if alt_source_col:
        alt_source_fields = extended_to_len(num_fields, alt_source_col)
        return [_clean_csv_field(field) for field in alt_source_fields]


def _get_alternate_source_fields_from_columns(worksheet, num_fields):
    matching_columns = sorted(get_columns_by_prefix(worksheet, 'alternate source field'), key=lambda x: x[0])
    alt_source_cols = [
        extended_to_len(num_fields, [cell.value if cell else cell for cell in alt_col])
        for col_name, alt_col in matching_columns
    ]
    # transpose columns to rows
    alt_srouce_fields = map(list, zip(*alt_source_cols))
    return [list(filter(None, fields)) for fields in alt_srouce_fields]


def get_alternate_source_fields(worksheet, num_fields):
    return (
        _get_alternate_source_fields_from_csv(worksheet, num_fields)
        or _get_alternate_source_fields_from_columns(worksheet, num_fields)
        or extended_to_len(num_fields, [])
    )


def compile_fields(worksheet, mappings=None):
    fields = without_empty_tail(get_column_by_name(worksheet, 'field') or [])

    if not fields:
        return []

    source_fields = extended_to_len(len(fields), get_column_by_name(worksheet, 'source field') or [])
    map_vias      = extended_to_len(len(fields), get_column_by_name(worksheet, 'map via') or [])
    format_vias   = extended_to_len(len(fields), get_column_by_name(worksheet, 'format via') or [])

    alternate_source_fields = get_alternate_source_fields(worksheet, len(fields))

    args = zip(fields, source_fields, alternate_source_fields, map_vias, format_vias)
    return [
        compile_field(
            field=field.value,
            source_field=source_field.value,
            alternate_source_fields=alt_source_fields,
            map_via=map_via.value if map_via else None,
            format_via=format_via.value if format_via else None,
            mappings=mappings
        )
        for field, source_field, alt_source_fields, map_via, format_via in args
    ]

def split_leftmost(jsonpath_expr):
    if isinstance(jsonpath_expr, jsonpath.Child):
        further_leftmost, rest = split_leftmost(jsonpath_expr.left)
        return further_leftmost, rest.child(jsonpath_expr.right)
    elif isinstance(jsonpath_expr, jsonpath.Descendants):
        further_leftmost, rest = split_leftmost(jsonpath_expr.left)
        return further_leftmost, jsonpath.Descendants(rest, jsonpath_expr.right)
    else:
        return (jsonpath_expr, jsonpath.This())


def compile_source(worksheet):
    """
    Compiles just the part of the Excel Spreadsheet that
    indicates the API endpoint to hit along with optional filters
    and an optional JSONPath within that endpoint, 

    For example, this spreadsheet
    
    Data Source                    Filter Name   Filter Value        Include Referenced Items
    -----------------------------  ------------  ------------------  --------------------------
    form[*].form.child_questions   app_id        <app id>            cases
                                   xmlns.exact   <some form xmlns>

    Should fetch from api/form?app_id=<app id>&xmlns.exact=<some form xmlns>&cases__full=true
    and then iterate (FlatMap) over all child questions.

    :return: tuple of the 'data source' expression and the 'root doc expression'.
        'data source': The MiniLinq that calls 'api_data' function to get data from CommCare
        'root doc expression': The MiniLinq that is applied to each doc, can be None.
    """

    data_source_column = get_column_by_name(worksheet, 'data source')
    if not data_source_column:
        raise Exception('Sheet has no "Data Source" column.')
    data_source_str = data_source_column[0].value
    filters = compile_filters(worksheet)
    include_referenced_items = [cell.value for cell in (get_column_by_name(worksheet, 'include referenced items') or [])]

    data_source, data_source_jsonpath = split_leftmost(parse_jsonpath(data_source_str))
    maybe_redundant_slice, remaining_jsonpath = split_leftmost(data_source_jsonpath)

    # The leftmost _must_ be of type Fields with one field and will pull out the first field
    if not isinstance(data_source, jsonpath.Fields) or len(data_source.fields) > 1:
        raise Exception('Bad value for data source: %s' % str(data_source))

    data_source = data_source.fields[0]

    if isinstance(maybe_redundant_slice, jsonpath.Slice):
        data_source_jsonpath = remaining_jsonpath

    api_query_args = [Reference("api_data"), Literal(data_source), Reference('checkpoint_manager')]
    
    if not filters:
        if include_referenced_items:
            api_query_args.append(Literal(None)) # Pad the argument list if we have further args; keeps tests and user code more readable at the expense of this conditional
    else:
        api_query_args.append(Literal(dict(filters)))

    if include_referenced_items:
        api_query_args.append(Literal(include_referenced_items))

    api_query = Apply(*api_query_args)

    if data_source_jsonpath is None or isinstance(data_source_jsonpath, jsonpath.This) or isinstance(data_source_jsonpath, jsonpath.Root):
        return data_source, api_query, None
    else:
        return data_source, api_query, Reference(str(data_source_jsonpath))

# If the source is expected to provide a column, then require that it is
# already present or can be added without conflicting with an existing
# column.
def require_column_in_sheet(sheet_name, data_source, table_name, output_headings,
                            output_fields, column_enforcer):
    # Check for conflicting use of column name.
    extend_fields = True

    required_column = column_enforcer.column_to_require(data_source)
    if required_column is None:
        extend_fields = False
    else:
        for i in range(len(output_headings)):
            if output_headings[i].value == required_column.name.v:
                if isinstance(output_fields[i], Reference) and \
                        output_fields[i].ref == required_column.source:
                    extend_fields = False
                    continue
                else:
                    raise Exception('Field name "{}" conflicts with an internal name.'.format(required_column.name.v))

    if extend_fields:
        headings = [Literal(output_heading.value)
                    for output_heading in output_headings] + [required_column.name]
        body = List(output_fields +
                    [compile_field(field=required_column.name,
                                   source_field=required_column.source)])
    else:
        headings = [Literal(output_heading.value)
                    for output_heading in output_headings]
        body = List(output_fields)

    return (headings, body)

def parse_sheet(worksheet, mappings=None, column_enforcer=None):
    mappings = mappings or {}
    data_source, source_expr, root_doc_expr = compile_source(worksheet)

    table_name_column = get_column_by_name(worksheet, 'table name')
    if table_name_column:
        output_table_name = table_name_column[0].value
    else:
        output_table_name = worksheet.title
    output_headings = get_column_by_name(worksheet, 'field')
    output_types = get_column_by_name(worksheet, 'data type') or []
    output_fields = compile_fields(worksheet, mappings=mappings)

    if not output_fields:
        headings = []
        data_types = []
        source = source_expr
        body = None
    else:
        # note: if we want to add data types to the columns added by the column_enforcer
        # this will have to conditionally move into the if/else below
        data_types = [Literal(data_type.value) for data_type in output_types]
        if column_enforcer is not None:
            (headings, body) = require_column_in_sheet(worksheet.title,
                                                       data_source,
                                                       output_table_name,
                                                       output_headings,
                                                       output_fields,
                                                       column_enforcer)
            source = source_expr
        else:
            headings = [Literal(output_heading.value)
                        for output_heading in output_headings]
            source = source_expr
            body = List(output_fields)

    return SheetParts(
        output_table_name,
        headings,
        source,
        body,
        root_doc_expr,
        data_types,
        data_source,
    )


class SheetParts(namedtuple('SheetParts', 'name headings source body root_expr data_types data_source')):
    def __new__(cls, name, headings, source, body, root_expr=None, data_types=None, data_source=None):
        data_types = data_types or []
        return super(SheetParts, cls).__new__(cls, name, headings, source, body, root_expr, data_types, data_source)

    @property
    def columns(self):
        return [
            col.v for col in self.headings
        ]


def parse_workbook(workbook, column_enforcer=None):
    """
    Returns a MiniLinq corresponding to the Excel configuration, which
    consists of the following sheets:

    1. "Mappings" a sheet with three columns that defines simple lookup table functions
       A. MappingName - the name by which this mapping is referenced
       B. Source - the value to match
       C. Destination - the value to return

    2. Each other sheet represents one data table to emit
    """
    try:
        mappings_sheet = workbook['Mappings']
    except KeyError:
        mappings_sheet = None
    mappings = compile_mappings(mappings_sheet) if mappings_sheet else None

    emit_sheets = [sheet_name for sheet_name in workbook.sheetnames if sheet_name != 'Mappings']

    parsed_sheets = []
    for sheet in emit_sheets:
        try:
            sheet_parts = parse_sheet(workbook[sheet], mappings, column_enforcer)
        except Exception as e:
            logger.warning('Ignoring sheet "{}": {}'.format(sheet, str(e)))
            continue

        parsed_sheets.append(sheet_parts)

    return parsed_sheets


def compile_queries(parsed_sheets, missing_value, combine_emits):
    # group sheets by source
    sheets_by_source = []
    for sheet in parsed_sheets:
        # Not easy to implement hashing on MiniLinq objects so can't use a dict
        for source, sheets in sheets_by_source:
            if sheet.source == source:
                sheets.append(sheet)
                break
        else:
            sheets_by_source.append((sheet.source, [sheet]))

    queries = []
    for source, sheets in sheets_by_source:
        if len(sheets) > 1:
            if combine_emits:
                queries.append(get_multi_emit_query(source, sheets, missing_value))
            else:
                queries.extend([
                    get_single_emit_query(sheet, missing_value)
                    for sheet in sheets
                ])
        else:
            queries.append(get_single_emit_query(sheets[0], missing_value))
    return queries


def get_multi_emit_query(source, sheets, missing_value):
    """Multiple `Emit` expressions using the same data source.
    For this we reverse the `Map` so that we apply each `Emit`
    repeatedly for each doc produced by the data source.
    """
    emits = []
    multi_query = Filter(  # the filter here is to prevent accumulating a `[None]` value for each doc
        predicate=Apply(
            Reference("filter_empty"),
            Reference("$")
        ),
        source=Map(
            source=source,
            body=List(emits)
        )
    )

    for sheet in sheets:
        # if there is no root expression then we just reference the whole document with `this`
        root_expr = sheet.root_expr or Reference("`this`")
        emits.append(
            Emit(
                table=sheet.name,
                headings=sheet.headings,
                source=Map(
                    source=root_expr,
                    body=sheet.body
                ),
                missing_value=missing_value,
                data_types=sheet.data_types,
            )
        )

    table_names = [sheet.name for sheet in sheets]
    data_source = sheets[0].data_source  # sheets will all have the same datasource
    return Bind('checkpoint_manager', Apply(
        Reference('get_checkpoint_manager'), Literal(data_source), Literal(table_names)
    ), multi_query)


def get_single_emit_query(sheet, missing_value):
    """Single `Emit` for the data source to we can just
    apply the `Emit` once with the source expression being
    the data source.
    """
    def _get_source(source, root_expr):
        if root_expr:
            return FlatMap(
                source=source,
                body=root_expr
            )
        else:
            return source

    emit = Emit(
        table=sheet.name,
        headings=sheet.headings,
        source=Map(
            source=_get_source(sheet.source, sheet.root_expr),
            body=sheet.body
        ),
        missing_value=missing_value,
        data_types=sheet.data_types,
    )
    return Bind('checkpoint_manager', Apply(
        Reference('get_checkpoint_manager'), Literal(sheet.data_source), Literal([sheet.name])
    ), emit)


def check_field_length(parsed_sheets, max_column_length):
    long_fields = defaultdict(list)
    for sheet in parsed_sheets:
        for col in sheet.columns:
            if len(col) > max_column_length:
                long_fields[sheet.name].append(col)

    if long_fields:
        raise LongFieldsException(long_fields, max_column_length)


def check_columns(parsed_sheets, columns):
    columns = set(columns)
    errors_by_sheet = {}
    for sheet in parsed_sheets:
        missing = columns - set(sheet.columns)
        if missing:
            errors_by_sheet[sheet.name] = list(missing)
    if errors_by_sheet:
        raise MissingColumnException(errors_by_sheet)

blacklisted_tables = []
def blacklist(table_name):
    blacklisted_tables.append(table_name)

def get_queries_from_excel(workbook, missing_value=None, combine_emits=False,
                           max_column_length=None, required_columns=None,
                           column_enforcer=None):
    parsed_sheets = parse_workbook(workbook, column_enforcer)
    for sheet in parsed_sheets:
        if sheet.name in blacklisted_tables:
            raise ReservedTableNameException(sheet.name)
    if max_column_length:
        check_field_length(parsed_sheets, max_column_length)
    if required_columns:
        check_columns(parsed_sheets, required_columns)
    queries = compile_queries(parsed_sheets, missing_value, combine_emits)
    return List(queries) if len(queries) > 1 else queries[0]
