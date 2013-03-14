from collections import defaultdict

from commcare_export.minilinq import *

def map_value(mappings_sheet, mapping_name, source_value):
    "From the mappings_sheet, replaces the source_value with appropriate output value"
    return source_value

def get_column_by_name(worksheet, column_name):
    for col in xrange(0, worksheet.get_highest_column()):
        if column_name == worksheet.cell(row=0, column=col).value:
            return [worksheet.cell(row=i, column=col) for i in xrange(1, worksheet.get_highest_row())]

def compile_mappings(worksheet):
    mapping_names = get_column_by_name(worksheet, "Mapping Name")
    sources       = extended_to_len(len(mapping_names), get_column_by_name(worksheet, "Source"))   
    destinations  = extended_to_len(len(mapping_names), get_column_by_name(worksheet, "Destination"))

    mappings = defaultdict(lambda: defaultdict(lambda: None))
    
    for mapping_name, source, dest in zip(mapping_names, sources, destinations):
        mappings[mapping_name.value][source.value] = dest.value

    return mappings

def compile_filters(worksheet, mappings=None):
    filter_names  = [cell.value for cell in get_column_by_name(worksheet, 'Filter Name') or []]

    if not filter_names:
        return []

    filter_values = extended_to_len(len(filter_names), [cell.value for cell in get_column_by_name(worksheet, 'Filter Value') or []])
    return zip(filter_names, filter_values)

def extended_to_len(desired_len, some_list, value=None):
    return [some_list[i] if i < len(some_list) else value
            for i in xrange(0, desired_len)]

def compile_field(field, source_field, map_via=None, format_via=None, mappings=None):
    expr = Reference(source_field)    

    if map_via:
        expr = Apply(Reference(map_via), expr)

    if format_via:
        expr = Apply(Reference(format_via), expr)

    return expr

def compile_fields(worksheet, mappings=None):
    fields = get_column_by_name(worksheet, 'Field')

    if not fields:
        return []

    source_fields = extended_to_len(len(fields), get_column_by_name(worksheet, 'Source Field') or [])
    map_vias      = extended_to_len(len(fields), get_column_by_name(worksheet, 'Map Via') or [])
    format_vias   = extended_to_len(len(fields), get_column_by_name(worksheet, 'Format Via') or [])

    return [compile_field(field        = field.value, 
                          source_field = source_field.value,
                          map_via      = map_via.value, 
                          format_via   = format_via.value,
                          mappings     = mappings)
            for field, source_field, map_via, format_via in zip(fields, source_fields, map_vias, format_vias)]

def compile_sheet(worksheet, mappings=None):
    mappings = mappings or {}
    data_source = get_column_by_name(worksheet, 'Data Source')[0].value
    filters = compile_filters(worksheet)

    if filters:
        api_query = Apply(Reference("api_data"), Literal(data_source), Literal(
            {'filter': {'and': [{'term': {filter_name: filter_value}} for filter_name, filter_value in filters]}}
        ))
    else:
        api_query = Apply(Reference("api_data"), Literal(data_source))

    output_table_name = worksheet.title
    output_headings = get_column_by_name(worksheet, 'Field') # It is unfortunate that this is duplicated here and in `compile_fields`
    output_fields = compile_fields(worksheet, mappings=mappings)

    if not output_fields:
        headings = headings = []
        source = api_query
    else:
        headings = [Literal(output_heading.value) for output_heading in output_headings]
        source = Map(source=api_query, body=List(output_fields))

    return Emit(table    = output_table_name, 
                headings = headings,
                source   = source)

def compile_workbook(workbook):
    """
    Returns a MiniLinq corresponding to the Excel configuration, which
    consists of the following sheets:

    1. "Mappings" a sheet with three columns that defines simple lookup table functions
       A. MappingName - the name by which this mapping is referenced
       B. Source - the value to match
       C. Destination - the value to return

    2. Each other sheet represents one data table to emit
    """
    queries = [] # A lit of queries will be built up; one per emit sheet
    
    emit_sheets = [sheet_name for sheet_name in workbook.get_sheet_names() if sheet_name != 'Mappings']

    for sheet in emit_sheets:
        queries.append(compile_sheet(sheet))

    return List(queries) # Moderate hack
    
    #mappings = workbook.get_sheet_by_name('Mappings')
    data_tables = workbook.get_sheet_by_name('Data Tables')
    columns = workbook.get_sheet_by_name('Columns')

    
    
