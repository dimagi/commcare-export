import unittest
import pprint
import os.path

import openpyxl

from commcare_export.minilinq import *
from commcare_export.excel_query import *

class TestExcelQuery(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_compile_sheet(self):

        test_cases = [
            ('001_JustDataSource.xlsx', Emit(table='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form")))),
            
            ('002_DataSourceAndFilters.xlsx', 
             Emit(table='Forms', 
                  headings=[], 
                  source=Apply(Reference("api_data"), 
                               Literal("form"),  
                               Literal({
                                   'filter': {
                                       'and': [
                                           {'term': { 'app_id': 'foobizzle' }},
                                           {'term': { 'type': 'intake' }}
                                        ]
                                   }
                        })))),

            ('003_DataSourceAndEmitColumns.xlsx',
             Emit(table    = 'Forms',
                  headings = [Literal('Form Type'), Literal('Fecha de Nacimiento'), Literal('Sexo')],
                  source   = Map(source = Apply(Reference("api_data"), Literal("form")),
                                 body   = List([
                                     Reference("type"),
                                     Apply(Reference("FormatDate"), Reference("date_of_birth")),
                                     Apply(Reference("sexo"), Reference("gender"))
                                 ])))),
        ]

        for filename, minilinq in test_cases:
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = compile_sheet(openpyxl.load_workbook(abs_path).get_active_sheet()) 
            # Print will be suppressed by pytest unless it fails
            if not (compiled == minilinq):
                print 'In', filename, ':'
                pprint.pprint(compiled.to_jvalue())
                print '!='
                pprint.pprint(minilinq.to_jvalue())
            assert compiled == minilinq
