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
            ('001_JustDataSource.xlsx', Apply(Reference("api_data"), Literal("form"))),
            
            ('002_DataSourceAndFilters.xlsx', 
             Apply(Reference("api_data"), 
                   Literal("form"), 
                   Literal({
                       'filter': {
                           'and': [
                               {'term': { 'app_id': 'foobizzle' }},
                               {'term': { 'type': 'intake' }}
                            ]
                        }
                   }))),
        ]

        for filename, minilinq in test_cases:
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = compile_sheet(openpyxl.load_workbook(abs_path).get_active_sheet()) 
            # Print will be suppressed by pytest unless it fails
            if not (compiled == minilinq):
                pprint.pprint(compiled.to_jvalue())
                print '!='
                pprint.pprint(minilinq.to_jvalue())
            assert compiled == minilinq
