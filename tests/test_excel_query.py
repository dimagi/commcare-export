from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import unittest
import pprint
import os.path
from collections import defaultdict

import openpyxl
from jsonpath_rw import jsonpath
from jsonpath_rw.parser import parse as parse_jsonpath

from commcare_export.minilinq import *
from commcare_export.excel_query import *

class TestExcelQuery(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_split_leftmost(self):
        assert split_leftmost(parse_jsonpath('foo')) == (jsonpath.Fields('foo'), jsonpath.This())
        assert split_leftmost(parse_jsonpath('foo.baz')) == (jsonpath.Fields('foo'), jsonpath.Fields('baz'))
        assert split_leftmost(parse_jsonpath('foo.baz.bar')) == (jsonpath.Fields('foo'), jsonpath.Fields('baz').child(jsonpath.Fields('bar')))
        assert split_leftmost(parse_jsonpath('[*].baz')) == (jsonpath.Slice(), jsonpath.Fields('baz'))
        assert split_leftmost(parse_jsonpath('foo[*].baz')) == (jsonpath.Fields('foo'), jsonpath.Slice().child(jsonpath.Fields('baz')))

    def test_compile_mappings(self):
        test_cases = [
            ('mappings.xlsx', 
             {
                 'a': {
                     'w': 12,
                     'x': 13,
                     'y': 14,
                     'z': 15,
                     'q': 16,
                     'r': 17,
                 },
                 'b': {
                     'www': 'hello',
                     'xxx': 'goodbye',
                     'yyy': 'what is up',
                 },
                 'c': {
                     1: 'foo',
                     2: 'bar',
                     3: 'biz',
                     4: 'bizzle',
                 }
             }),
        ]

        def flatten(dd):
            if isinstance(dd, defaultdict):
                return dict([(key, flatten(val)) for key, val in dd.items()])
            else:
                return dd

        for filename, mappings in test_cases:
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = compile_mappings(openpyxl.load_workbook(abs_path).get_sheet_by_name('Mappings'))
            # Print will be suppressed by pytest unless it fails
            if not (flatten(compiled) == mappings):
                print('In %s:' % filename)
                pprint.pprint(flatten(compiled))
                print('!=')
                pprint.pprint(mappings)
            assert flatten(compiled) == mappings

    def test_compile_sheet(self):

        test_cases = [
            ('001_JustDataSource.xlsx', Emit(table='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form")))),
            ('001a_JustDataSource_LibreOffice.xlsx', Emit(table='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form")))),
            
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

            ('005_DataSourcePath.xlsx',
             Emit(table    = 'Forms',
                  headings = [],
                  source   = FlatMap(source = Apply(Reference("api_data"), Literal("form")),
                                     body   = Reference('form.delivery_information.child_questions.[*]')))),

            ('006_IncludeReferencedItems.xlsx',
             Emit(table='Forms',
                  headings=[],
                  source=Apply(Reference("api_data"), 
                               Literal("form"),
                               Literal(None),
                               Literal(['foo', 'bar', 'bizzle']))))
        ]

        for filename, minilinq in test_cases:
            print('Compiling sheet %s' % filename) # This output will be captured by pytest and printed in case of failure; helpful to isolate which test case
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = compile_sheet(openpyxl.load_workbook(abs_path).get_active_sheet()) 
            # Print will be suppressed by pytest unless it fails
            if not (compiled == minilinq):
                print('In %s:' % filename)
                pprint.pprint(compiled.to_jvalue())
                print('!=')
                pprint.pprint(minilinq.to_jvalue())
            assert compiled == minilinq

    def test_compile_workbook(self):
        test_cases = [
            ('004_TwoDataSources.xlsx', 
             List([ 
                Emit(table='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form"))),
                Emit(table='Cases', headings=[], source=Apply(Reference("api_data"), Literal("case")))
             ]))
        ]

        for filename, minilinq in test_cases:
            print('Compiling workbook %s' % filename) # This output will be captured by pytest and printed in case of failure; helpful to isolate which test case
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = compile_workbook(openpyxl.load_workbook(abs_path))
            # Print will be suppressed by pytest unless it fails
            if not (compiled == minilinq):
                print('In %s:' % filename)
                pprint.pprint(compiled.to_jvalue())
                print('!=')
                pprint.pprint(minilinq.to_jvalue())
            assert compiled == minilinq
