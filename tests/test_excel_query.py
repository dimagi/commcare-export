import unittest
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
        ]

        for filename, minilinq in test_cases:
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = compile_sheet(openpyxl.load_workbook(abs_path).get_active_sheet()) 
            assert compiled == minilinq
