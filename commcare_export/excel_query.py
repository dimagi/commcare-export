
from minilinq import *
    
def compile(workbook):
    """
    Returns a MiniLinq corresponding to the Excel configuration, which
    consists of the following sheets:

    1. Mappings, a sheet with three columns that defines simple lookup table functions
       A. MappingName - the name by which this mapping is referenced
       B. Source - the value to match
       C. Destination - the value to return

    2. Data sources, a sheet that configures the data records the report is built from
    3. Columns, a sheet that configures the columns to start with
    """
    
