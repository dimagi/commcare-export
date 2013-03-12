
from commcare_export.minilinq import *

def map_value(mappings_sheet, mapping_name, source_value):
    "From the mappings_sheet, replaces the source_value with appropriate output value"
    return source_value

def get_column_by_name(worksheet, column_name):
    for col in xrange(0, worksheet.get_highest_column()):
        if column_name == worksheet.cell(row=0, column=col).value:
            return [worksheet.cell(row=i, column=col) for i in xrange(1, worksheet.get_highest_row())]

def compile_sheet(worksheet, mappings=None):
    mappings = mappings or {}

    data_source = get_column_by_name(worksheet, 'Data Source')[0].value

    return Apply(Reference("api_data"), Literal(data_source))

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

    
    
