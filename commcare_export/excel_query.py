from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import re
from collections import defaultdict

from six.moves import xrange

from jsonpath_rw import jsonpath
from jsonpath_rw.parser import parse as parse_jsonpath

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
    for col in xrange(1, worksheet.get_highest_column() + 1):
        value = worksheet.cell(row=1, column=col).value
        value = value.lower() if value else value
        if column_name == value:
            return without_empty_tail([
                worksheet.cell(row=i, column=col) for i in xrange(2, worksheet.get_highest_row() + 1)
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

def compile_field(field, source_field, map_via=None, format_via=None, mappings=None):
    expr = Reference(source_field)    

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



def compile_fields(worksheet, mappings=None):
    fields = without_empty_tail(get_column_by_name(worksheet, 'field') or [])

    if not fields:
        return []

    source_fields = extended_to_len(len(fields), get_column_by_name(worksheet, 'source field') or [])
    map_vias      = extended_to_len(len(fields), get_column_by_name(worksheet, 'map via') or [])
    format_vias   = extended_to_len(len(fields), get_column_by_name(worksheet, 'format via') or [])

    return [compile_field(field        = field.value, 
                          source_field = source_field.value,
                          map_via      = map_via.value if map_via else None, 
                          format_via   = format_via.value if format_via else None,
                          mappings     = mappings)
            for field, source_field, map_via, format_via in zip(fields, source_fields, map_vias, format_vias)]

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

    api_query_args = [Reference("api_data"), Literal(data_source)]
    
    if not filters:
        if include_referenced_items:
            api_query_args.append(Literal(None)) # Pad the argument list if we have further args; keeps tests and user code more readable at the expense of this conditional
    else:
        api_query_args.append(Literal(dict(filters)))

    if include_referenced_items:
        api_query_args.append(Literal(include_referenced_items))

    api_query = Apply(*api_query_args)

    if data_source_jsonpath is None or isinstance(data_source_jsonpath, jsonpath.This) or isinstance(data_source_jsonpath, jsonpath.Root):
        return api_query
    else:
        return FlatMap(source=api_query,
                       body=Reference(str(data_source_jsonpath)))

def compile_sheet(worksheet, mappings=None, missing_value=None):
    mappings = mappings or {}
    source_expr = compile_source(worksheet)

    output_table_name = worksheet.title
    output_headings = get_column_by_name(worksheet, 'field') # It is unfortunate that this is duplicated here and in `compile_fields`
    output_fields = compile_fields(worksheet, mappings=mappings)

    if not output_fields:
        headings = headings = []
        source = source_expr
    else:
        headings = [Literal(output_heading.value) for output_heading in output_headings]
        source = Map(source=source_expr, body=List(output_fields))

    return Emit(
        table=output_table_name,
        headings=headings,
        source=source,
        missing_value=missing_value
    )

def compile_workbook(workbook, missing_value=None):
    """
    Returns a MiniLinq corresponding to the Excel configuration, which
    consists of the following sheets:

    1. "Mappings" a sheet with three columns that defines simple lookup table functions
       A. MappingName - the name by which this mapping is referenced
       B. Source - the value to match
       C. Destination - the value to return

    2. Each other sheet represents one data table to emit
    """
    mappings_sheet = workbook.get_sheet_by_name('Mappings')
    mappings = compile_mappings(mappings_sheet) if mappings_sheet else None

    queries = [] # A lit of queries will be built up; one per emit sheet
    
    emit_sheets = [sheet_name for sheet_name in workbook.get_sheet_names() if sheet_name != 'Mappings']

    for sheet in emit_sheets:
        try:
            queries.append(compile_sheet(workbook.get_sheet_by_name(sheet), mappings, missing_value))
        except Exception as e:
            logger.warning('Ignoring sheet "{}": {}'.format(sheet, str(e)))

    return List(queries) # Moderate hack
    
    
    
