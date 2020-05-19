from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import os.path
import pprint
import unittest

import openpyxl

from commcare_export.env import BuiltInEnv
from commcare_export.env import JsonPathEnv
from commcare_export.excel_query import *
from commcare_export.excel_query import _get_safe_source_field
from commcare_export.builtin_queries import ColumnEnforcer


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

    def test_get_safe_source_field(self):
        assert _get_safe_source_field('foo.bar.baz') == Reference('foo.bar.baz')
        assert _get_safe_source_field('foo[*].baz') == Reference('foo[*].baz')
        assert _get_safe_source_field('foo..baz[*]') == Reference('foo..baz[*]')
        assert _get_safe_source_field('foo.#baz') == Reference('foo."#baz"')
        assert _get_safe_source_field('foo.bar[*]..%baz') == Reference('foo.bar[*].."%baz"')
        assert _get_safe_source_field('foo.bar:1.baz') == Reference('foo."bar:1".baz')

        try:
            assert _get_safe_source_field('foo.bar.')
            assert False, "Expected exception"
        except Exception:
            pass

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
            compiled = compile_mappings(openpyxl.load_workbook(abs_path)['Mappings'])
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
                name='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')), body=None),
            ),
            #('001a_JustDataSource_LibreOffice.xlsx', Emit(table='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form")))),
            
            ('002_DataSourceAndFilters.xlsx',
             SheetParts(
                 name='Forms',
                 headings=[],
                 source=Apply(
                     Reference("api_data"),
                     Literal("form"),
                     Reference("checkpoint_manager"),
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
                     Literal('Danger error'), Literal('Danger error'), Literal('special')
                 ],
                 source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
                 body=List([
                     Reference("type"),
                     Apply(Reference("FormatDate"), Reference("date_of_birth")),
                     Apply(Reference("sexo"), Reference("gender")),
                     Apply(Reference("selected-at"), Reference("dangers"), Literal(0)),
                     Apply(Reference("selected-at"), Reference("dangers"), Literal(1)),
                     Apply(Reference("selected"), Reference("dangers"), Literal('fever')),
                     Literal('Error: selected-at index must be an integer: selected-at(abc)'),
                     Literal('Error: Unable to parse: selected(fever'),
                     Reference('path."#text"')
                 ])
             )),

            ('005_DataSourcePath.xlsx',
             SheetParts(
                 name='Forms',
                 headings = [],
                 source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
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
                     Reference("checkpoint_manager"),
                     Literal(None),
                     Literal(['foo', 'bar', 'bizzle'])
                 ),
                 body=None
             )),

            ('010_JustDataSourceTableName.xlsx', SheetParts(
                name='my_table', headings=[], source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')), body=None),
            ),
        ]

        for filename, minilinq in test_cases:
            print('Compiling sheet %s' % filename) # This output will be captured by pytest and printed in case of failure; helpful to isolate which test case
            abs_path = os.path.join(os.path.dirname(__file__), filename)
            compiled = parse_sheet(openpyxl.load_workbook(abs_path).active)
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
                SheetParts(name='Forms', headings=[], source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')), body=None),
                SheetParts(name='Cases', headings=[], source=Apply(Reference("api_data"), Literal("case"), Reference('checkpoint_manager')), body=None)
             ]),
            ('007_Mappings.xlsx',
             [
                 SheetParts(
                     name='Forms',
                     headings=[Literal('Form Type')],
                     source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
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

        expression = compile_mapped_field({'a': 'mapped from a'}, Reference('foo.boo'))
        assert list(expression.eval(env)) == []

    def test_get_queries_from_excel(self):
        minilinq = Bind('checkpoint_manager', Apply(Reference('get_checkpoint_manager'), Literal(["Forms"])),
            Emit(
            table='Forms',
            missing_value='---',
            headings =[
                Literal('Form Type'), Literal('Fecha de Nacimiento'), Literal('Sexo'),
                Literal('Danger 0'), Literal('Danger 1'), Literal('Danger Fever'),
                Literal('Danger error'), Literal('Danger error'), Literal('special')
            ],
            source = Map(
                source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
                body = List([
                    Reference("type"),
                    Apply(Reference("FormatDate"), Reference("date_of_birth")),
                    Apply(Reference("sexo"), Reference("gender")),
                    Apply(Reference("selected-at"), Reference("dangers"), Literal(0)),
                    Apply(Reference("selected-at"), Reference("dangers"), Literal(1)),
                    Apply(Reference("selected"), Reference("dangers"), Literal('fever')),
                    Literal('Error: selected-at index must be an integer: selected-at(abc)'),
                    Literal('Error: Unable to parse: selected(fever'),
                    Reference('path."#text"')
                ]))
            )
        )

        self._compare_minilinq_to_compiled(minilinq, '003_DataSourceAndEmitColumns.xlsx')

    def test_alternate_source_fields(self):
        minilinq = List([
            # First sheet uses a CSV column and also tests combining "Map Via"
            Bind('checkpoint_manager', Apply(Reference('get_checkpoint_manager'), Literal(["Forms"])),
                Emit(
                    table='Forms', missing_value='---',
                    headings =[
                        Literal('dob'),
                    ],
                    source = Map(
                        source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
                        body = List([
                            Apply(
                                Reference("str2date"),
                                Apply(
                                    Reference("or"),
                                    Reference("dob"), Reference("date_of_birth"), Reference("d_o_b")
                                )
                            ),
                        ]))
                )
            ),

            # Second sheet uses multiple alternate source field columns (listed out of order)
            Bind('checkpoint_manager', Apply(Reference('get_checkpoint_manager'), Literal(["Forms1"])),
                Emit(
                    table='Forms1', missing_value='---',
                    headings=[
                        Literal('dob'), Literal('Sex'),
                    ],
                    source=Map(
                        source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
                        body=List([
                            Reference("dob"),
                            Apply(
                                Reference("or"),
                                Reference("gender"), Reference("sex"), Reference("sex0")
                            )
                        ]))
                )
            ),
        ])

        self._compare_minilinq_to_compiled(minilinq, '011_AlternateSourceFields.xlsx')

    def test_multi_emit(self):
        minilinq = List([
            Bind("checkpoint_manager", Apply(Reference('get_checkpoint_manager'), Literal(["Forms", "Cases"])),
                Filter(
                    predicate=Apply(
                        Reference("filter_empty"),
                        Reference("$")
                    ),
                    source=Map(
                        source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
                        body=List([
                            Emit(
                                table="Forms",
                                headings=[Literal("id"), Literal("name")],
                                missing_value='---',
                                source=Map(
                                    source=Reference("`this`"),
                                    body=List([
                                        Reference("id"),
                                        Reference("form.name"),
                                    ]),
                                )
                            ),
                            Emit(
                                table="Cases",
                                headings=[Literal("case_id")],
                                missing_value='---',
                                source=Map(
                                    source=Reference("form..case"),
                                    body=List([
                                        Reference("@case_id"),
                                    ]),
                                )
                            )
                        ])
                    )
                )
            ),
            Bind(
                'checkpoint_manager',
                Apply(Reference('get_checkpoint_manager'), Literal(["Other cases"])),
                Emit(
                    table="Other cases",
                    headings=[Literal("id")],
                    missing_value='---',
                    source=Map(
                        source=Apply(Reference("api_data"), Literal("case"), Reference('checkpoint_manager')),
                        body=List([
                            Reference("id")
                        ])
                    )
                )
            )
        ])

        self._compare_minilinq_to_compiled(minilinq, '008_multiple-tables.xlsx', combine=True)

    def test_multi_emit_no_combine(self):
        minilinq = List([
            Bind("checkpoint_manager", Apply(Reference('get_checkpoint_manager'), Literal(["Forms"])),
                 Emit(
                    table="Forms",
                    headings=[Literal("id"), Literal("name")],
                    missing_value='---',
                    source=Map(
                        source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
                        body=List([
                            Reference("id"),
                            Reference("form.name"),
                        ]),
                    )
                 )
            ),
            Bind("checkpoint_manager", Apply(Reference('get_checkpoint_manager'), Literal(["Cases"])),
                Emit(
                    table="Cases",
                    headings=[Literal("case_id")],
                    missing_value='---',
                    source=Map(
                        source=FlatMap(
                            body=Reference("form..case"),
                            source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager'))
                        ),
                        body=List([
                            Reference("@case_id"),
                        ]),
                    )
                )
            ),
            Bind("checkpoint_manager", Apply(Reference('get_checkpoint_manager'), Literal(["Other cases"])),
                Emit(
                    table="Other cases",
                    headings=[Literal("id")],
                    missing_value='---',
                    source=Map(
                        source=Apply(Reference("api_data"), Literal("case"), Reference('checkpoint_manager')),
                        body=List([
                            Reference("id")
                        ])
                    )
                )
            )
        ])

        self._compare_minilinq_to_compiled(minilinq, '008_multiple-tables.xlsx', combine=False)

    def test_multi_emit_with_organization(self):
        minilinq = List([
            Bind("checkpoint_manager", Apply(Reference('get_checkpoint_manager'), Literal(["Forms", "Cases"])),
                Filter(
                    predicate=Apply(
                        Reference("filter_empty"),
                        Reference("$")
                    ),
                    source=Map(
                        source=Apply(Reference("api_data"), Literal("form"), Reference('checkpoint_manager')),
                        body=List([
                            Emit(
                                table="Forms",
                                headings=[Literal("id"), Literal("name"), Literal("commcare_userid")],
                                missing_value='---',
                                source=Map(
                                    source=Reference("`this`"),
                                    body=List([
                                        Reference("id"),
                                        Reference("form.name"),
                                        Reference("$.metadata.userID"),
                                    ]),
                                )
                            ),
                            Emit(
                                table="Cases",
                                headings=[Literal("case_id"), Literal("commcare_userid")],
                                missing_value='---',
                                source=Map(
                                    source=Reference("form..case"),
                                    body=List([
                                        Reference("@case_id"),
                                        Reference("$.metadata.userID"),
                                    ]),
                                )
                            )
                        ])
                    )
                )
            ),
            Bind(
                'checkpoint_manager',
                Apply(Reference('get_checkpoint_manager'), Literal(["Other cases"])),
                Emit(
                    table="Other cases",
                    headings=[Literal("id"), Literal("commcare_userid")],
                    missing_value='---',
                    source=Map(
                        source=Apply(Reference("api_data"), Literal("case"), Reference('checkpoint_manager')),
                        body=List([
                            Reference("id"),
                            Reference("$.user_id")
                        ])
                    )
                )
            )
        ])

        column_enforcer = ColumnEnforcer()
        self._compare_minilinq_to_compiled(minilinq, '008_multiple-tables.xlsx', combine=True,
                                           column_enforcer=column_enforcer)

    def _compare_minilinq_to_compiled(self, minilinq, filename, combine=False, column_enforcer=None):
        print("Parsing {}".format(filename))
        abs_path = os.path.join(os.path.dirname(__file__), filename)
        compiled = get_queries_from_excel(openpyxl.load_workbook(abs_path), missing_value='---', combine_emits=combine, column_enforcer=column_enforcer)
        assert compiled.to_jvalue() == minilinq.to_jvalue(), filename
