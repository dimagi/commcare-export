from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import os.path
import pprint
import unittest

import openpyxl

from commcare_export.env import BuiltInEnv
from commcare_export.env import JsonPathEnv
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

    def test_parse_sheet(self):

        test_cases = [
            ('001_JustDataSource.xlsx', SheetParts(
                name='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form")), body=None),
            ),
            #('001a_JustDataSource_LibreOffice.xlsx', Emit(table='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form")))),
            
            ('002_DataSourceAndFilters.xlsx',
             SheetParts(
                 name='Forms',
                 headings=[],
                 source=Apply(
                     Reference("api_data"),
                     Literal("form"),
                     Literal({
                         'app_id': 'foobizzle',
                         'type': 'intake',
                     })
                 ),
                 body=None
             )),

            ('003_DataSourceAndEmitColumns.xlsx',
             SheetParts(
                 name='Forms',
                 headings = [
                     Literal('Form Type'), Literal('Fecha de Nacimiento'), Literal('Sexo'),
                     Literal('Danger 0'), Literal('Danger 1'), Literal('Danger Fever'),
                     Literal('Danger error'), Literal('Danger error')
                 ],
                 source=Apply(Reference("api_data"), Literal("form")),
                 body=List([
                     Reference("type"),
                     Apply(Reference("FormatDate"), Reference("date_of_birth")),
                     Apply(Reference("sexo"), Reference("gender")),
                     Apply(Reference("selected-at"), Reference("dangers"), Literal(0)),
                     Apply(Reference("selected-at"), Reference("dangers"), Literal(1)),
                     Apply(Reference("selected"), Reference("dangers"), Literal('fever')),
                     Literal('Error: selected-at index must be an integer: selected-at(abc)'),
                     Literal('Error: Unable to parse: selected(fever'),
                 ])
             )),

            ('005_DataSourcePath.xlsx',
             SheetParts(
                 name='Forms',
                 headings = [],
                 source=Apply(Reference("api_data"), Literal("form")),
                 body=None,
                 root_expr=Reference('form.delivery_information.child_questions.[*]')
             )),

            ('006_IncludeReferencedItems.xlsx',
             SheetParts(
                 name='Forms',
                 headings=[],
                 source=Apply(
                     Reference("api_data"),
                     Literal("form"),
                     Literal(None),
                     Literal(['foo', 'bar', 'bizzle'])
                 ),
                 body=None
             )),
        ]

        for filename, minilinq in test_cases:
            print('Compiling sheet %s' % filename) # This output will be captured by pytest and printed in case of failure; helpful to isolate which test case
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = parse_sheet(openpyxl.load_workbook(abs_path).get_active_sheet())
            # Print will be suppressed by pytest unless it fails
            if not (compiled == minilinq):
                print('In %s:' % filename)
                pprint.pprint(compiled)
                print('!=')
                pprint.pprint(minilinq)
            assert compiled == minilinq

    def test_parse_workbook(self):
        field_mappings = {'t1': 'Form 1', 't2': 'Form 2'}
        test_cases = [
            ('004_TwoDataSources.xlsx', 
             [
                SheetParts(name='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form")), body=None),
                SheetParts(name='Cases', headings=[], source=Apply(Reference("api_data"), Literal("case")), body=None)
             ]),
            ('007_Mappings.xlsx',
             [
                 SheetParts(
                     name='Forms',
                     headings=[Literal('Form Type')],
                     source=Apply(Reference("api_data"), Literal("form")),
                     body=List([compile_mapped_field(field_mappings, Reference("type"))]),
                 )
             ]),

        ]

        for filename, minilinq in test_cases:
            print('Compiling workbook %s' % filename) # This output will be captured by pytest and printed in case of failure; helpful to isolate which test case
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = parse_workbook(openpyxl.load_workbook(abs_path))
            # Print will be suppressed by pytest unless it fails
            if not (compiled == minilinq):
                print('In %s:' % filename)
                pprint.pprint(compiled)
                print('!=')
                pprint.pprint(minilinq)
            assert compiled == minilinq

    def test_compile_mapped_field(self):
        env = BuiltInEnv() | JsonPathEnv({'foo': {'bar': 'a', 'baz': 'b'}})
        expression = compile_mapped_field({'a': 'mapped from a'}, Reference('foo.bar'))
        assert expression.eval(env) == 'mapped from a'

        expression = compile_mapped_field({'a': 'mapped from a'}, Reference('foo.baz'))
        assert list(expression.eval(env))[0].value == 'b'

    def test_get_queries_from_excel(self):
        minilinq = Emit(
            table='Forms',
            missing_value='---',
            headings =[
                Literal('Form Type'), Literal('Fecha de Nacimiento'), Literal('Sexo'),
                Literal('Danger 0'), Literal('Danger 1'), Literal('Danger Fever'),
                Literal('Danger error'), Literal('Danger error')
            ],
            source = Map(
                source=Apply(Reference("api_data"), Literal("form")),
                body = List([
                    Reference("type"),
                    Apply(Reference("FormatDate"), Reference("date_of_birth")),
                    Apply(Reference("sexo"), Reference("gender")),
                    Apply(Reference("selected-at"), Reference("dangers"), Literal(0)),
                    Apply(Reference("selected-at"), Reference("dangers"), Literal(1)),
                    Apply(Reference("selected"), Reference("dangers"), Literal('fever')),
                    Literal('Error: selected-at index must be an integer: selected-at(abc)'),
                    Literal('Error: Unable to parse: selected(fever'),
                ]))
        )

        filename = '003_DataSourceAndEmitColumns.xlsx'
        abs_path = os.path.join(os.path.dirname(__file__), filename)
        compiled = get_queries_from_excel(openpyxl.load_workbook(abs_path), missing_value='---')
        # Print will be suppressed by pytest unless it fails
        if not (compiled == minilinq):
            print('In %s:' % filename)
            pprint.pprint(compiled.to_jvalue())
            print('!=')
            pprint.pprint(minilinq.to_jvalue())
        assert compiled == minilinq

