import types
import unittest
from datetime import datetime
from itertools import *

import pytest
from commcare_export.env import *
from commcare_export.excel_query import get_value_or_root_expression
from commcare_export.minilinq import *
from commcare_export.writers import JValueTableWriter


class LazinessException(Exception):
    pass


def die(msg):
    # Hack: since "raise" is a statement not an expression, need a
    # funcall wrapping it
    raise LazinessException(msg)


class TestMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def check_case(self, val, expected):
        if isinstance(expected, list):
            assert [unwrap_val(datum) for datum in val] == expected
        else:
            assert val == expected

    def test_eval_literal(self):
        env = BuiltInEnv()
        assert Literal("foo").eval(env) == "foo"
        assert Literal(2).eval(env) == 2
        assert Literal({'foo': 'baz'}).eval(env) == {'foo': 'baz'}

    def test_eval_reference(self):
        env = BuiltInEnv()
        assert Reference("foo").eval(DictEnv({'foo': 2})) == 2
        assert Reference(Reference(Reference('a'))
                        ).eval(DictEnv({
                            'a': 'b',
                            'b': 'c',
                            'c': 2
                        })) == 2
        self.check_case(
            Reference("foo[*]").eval(JsonPathEnv({'foo': [2]})), [2]
        )
        # Should work the same w/ iterators as with lists
        self.check_case(
            Reference("foo[*]").eval(JsonPathEnv({'foo': range(0, 1)})), [0]
        )

        # Should be able to get back out to the root, as the JsonPathEnv
        # actually passes the full datum around
        self.check_case(
            Reference("foo.$.baz").eval(JsonPathEnv({
                'foo': [2],
                'baz': 3
            })), [3]
        )

    def test_eval_auto_id_reference(self):
        """
        Test that we have turned on the jsonpath_ng.jsonpath.auto_id
        field properly
        """
        env = BuiltInEnv()

        self.check_case(
            Reference("foo.id").eval(JsonPathEnv({'foo': [2]})), ['foo']
        )

        # When auto id is on, this always becomes a string. Sorry!
        self.check_case(
            Reference("foo.id").eval(JsonPathEnv({'foo': {
                'id': 2
            }})), ['2']
        )

    def test_eval_auto_id_reference_nested(self):
        # this test is documentation of existing (weird) functionality
        # that results from a combination of jsonpath_ng auto_id feature
        # and JsonPathEnv.lookup (which adds an additional auto ID for
        # some reason).
        env = JsonPathEnv({})

        flatmap = FlatMap(
            source=Literal([{
                "id": 1,
                "foo": {
                    'id': 'bid',
                    'name': 'bob'
                },
                "bar": [{
                    'baz': 'a1'
                }, {
                    'baz': 'a2',
                    'id': 'bazzer'
                }]
            }]),
            body=Reference('bar.[*]')
        )
        mmap = Map(
            source=flatmap,
            body=List([
                Reference("id"),
                Reference('baz'),
                Reference('$.id'),
                Reference('$.foo.id'),
                Reference('$.foo.name')
            ])
        )
        self.check_case(
            mmap.eval(env), [["1.bar.'1.bar.[0]'", 'a1', '1', '1.bid', 'bob'],
                             ['1.bar.bazzer', 'a2', '1', '1.bid', 'bob']]
        )

        # Without the additional auto id field added in JsonPathEnv the
        # result for Reference("id") changes as follows:
        #   '1.bar.1.bar.[0]' -> '1.bar.[0]'

        # With the change above AND a change to jsonpath_ng to prevent
        # converting IDs that exist into auto IDs (see
        # https://github.com/kennknowles/python-jsonpath-rw/pull/96) we
        # get the following:
        #   Reference("id"):
        #       '1.bar.bazzer' -> 'bazzer'
        #
        #   Reference('$.foo.id'):
        #       '1.bid' -> 'bid'

    def test_value_or_root(self):
        """
        Test that when accessing a child object the child data is used
        if it exists (normal case).
        """
        data = {"id": 1, "bar": [{'baz': 'a1'}, {'baz': 'a2'}]}
        self._test_value_or_root([Reference('id'),
                                  Reference('baz')], data, [
                                      ["1.bar.'1.bar.[0]'", 'a1'],
                                      ["1.bar.'1.bar.[1]'", 'a2'],
                                  ])

    def test_value_or_root_empty_list(self):
        """Should use the root object if the child is an empty list"""
        data = {
            "id": 1,
            "foo": "I am foo",
            "bar": [],
        }
        self._test_value_or_root([
            Reference('id'),
            Reference('baz'),
            Reference('$.foo')
        ], data, [
            ['1', [], "I am foo"],
        ])

    def test_value_or_root_empty_dict(self):
        """Should use the root object if the child is an empty dict"""
        data = {
            "id": 1,
            "foo": "I am foo",
            "bar": {},
        }
        self._test_value_or_root([
            Reference('id'),
            Reference('baz'),
            Reference('$.foo')
        ], data, [
            ['1', [], "I am foo"],
        ])

    def test_value_or_root_None(self):
        """Should use the root object if the child is None"""
        data = {
            "id": 1,
            "bar": None,
        }
        self._test_value_or_root([Reference('id'),
                                  Reference('baz')], data, [
                                      ['1', []],
                                  ])

    def test_value_or_root_missing(self):
        """Should use the root object if the child does not exist"""
        data = {
            "id": 1,
            "foo": "I am foo",
            # 'bar' is missing
        }
        self._test_value_or_root([
            Reference('id'),
            Reference('baz'),
            Reference('$.foo')
        ], data, [
            ['1', [], 'I am foo'],
        ])

    def test_value_or_root_ignore_field_in_root(self):
        """
        Test that a child reference is ignored if we are using the root
        doc even if there is a field with that name. (this doesn't apply
        to 'id')
        """
        data = {
            "id": 1,
            "foo": "I am foo",
        }
        self._test_value_or_root([Reference('id'),
                                  Reference('foo')], data, [
                                      ['1', []],
                                  ])

    def _test_value_or_root(self, columns, data, expected):
        """Low level test case for 'value-or-root'"""
        env = BuiltInEnv() | JsonPathEnv({})
        value_or_root = get_value_or_root_expression('bar.[*]')
        flatmap = FlatMap(source=Literal([data]), body=value_or_root)
        mmap = Map(source=flatmap, body=List(columns))
        self.check_case(mmap.eval(env), expected)

    def test_eval_collapsed_list(self):
        """
        Special case to handle XML -> JSON conversion where there just
        happened to be a single value at save time
        """
        env = BuiltInEnv()
        self.check_case(Reference("foo[*]").eval(JsonPathEnv({'foo': 2})), [2])
        assert Apply(Reference("*"), Literal(2), Literal(3)).eval(env) == 6
        assert Apply(Reference(">"), Literal(56),
                     Literal(23.5)).eval(env) == True
        assert Apply(Reference("len"), Literal([1, 2, 3])).eval(env) == 3
        assert Apply(Reference("bool"), Literal('a')).eval(env) == True
        assert Apply(Reference("bool"), Literal('')).eval(env) == False
        assert Apply(Reference("str2bool"), Literal('true')).eval(env) == True
        assert Apply(Reference("str2bool"), Literal('t')).eval(env) == True
        assert Apply(Reference("str2bool"), Literal('1')).eval(env) == True
        assert Apply(Reference("str2bool"), Literal('0')).eval(env) == False
        assert Apply(Reference("str2bool"),
                     Literal('false')).eval(env) == False
        assert Apply(Reference("str2bool"), Literal(u'日本')).eval(env) == False
        assert Apply(Reference("str2num"), Literal('10')).eval(env) == 10
        assert Apply(Reference("str2num"), Literal('10.56')).eval(env) == 10.56
        assert Apply(Reference("str2num"), Literal('')).eval(env) == None
        assert Apply(Reference("str2date"),
                     Literal('2015-01-01')).eval(env) == datetime(2015, 1, 1)
        assert Apply(Reference("str2date"), Literal('2015-01-01T18:32:57')
                    ).eval(env) == datetime(2015, 1, 1, 18, 32, 57)
        assert Apply(
            Reference("str2date"), Literal('2015-01-01T18:32:57.001200')
        ).eval(env) == datetime(2015, 1, 1, 18, 32, 57)
        assert Apply(
            Reference("str2date"), Literal('2015-01-01T18:32:57.001200Z')
        ).eval(env) == datetime(2015, 1, 1, 18, 32, 57)
        assert Apply(Reference("str2date"),
                     Literal(u'日'.encode('utf8'))).eval(env) == None
        assert Apply(Reference("str2date"), Literal(u'日')).eval(env) == None
        assert Apply(Reference("format-uuid"),
                     Literal(0xf00)).eval(env) == None
        assert Apply(Reference("format-uuid"),
                     Literal('f00')).eval(env) == None
        assert Apply(
            Reference("format-uuid"),
            Literal('00a3e019-4ce1-4587-94c5-0971dee2de22')
        ).eval(env) == '00a3e019-4ce1-4587-94c5-0971dee2de22'
        assert Apply(Reference("selected-at"), Literal('a b c'),
                     Literal('1')).eval(env) == 'b'
        assert Apply(
            Reference("selected-at"), Literal(u'a b 日'), Literal('-1')
        ).eval(env) == u'日'
        assert Apply(Reference("selected-at"), Literal('a b c'),
                     Literal('5')).eval(env) is None
        assert Apply(Reference("selected"), Literal('a b c'),
                     Literal('b')).eval(env) is True
        assert Apply(Reference("selected"), Literal(u'a b 日本'),
                     Literal('d')).eval(env) is False
        assert Apply(Reference("selected"), Literal(u'a bb 日本'),
                     Literal('b')).eval(env) is False
        assert Apply(
            Reference("selected"), Literal(u'a bb 日本'), Literal(u'日本')
        ).eval(env) is True
        assert Apply(
            Reference("join"), Literal('.'), Literal('a'), Literal('b'),
            Literal('c')
        ).eval(env) == 'a.b.c'
        assert Apply(Reference("default"), Literal(None),
                     Literal('a')).eval(env) == 'a'
        assert Apply(Reference("default"), Literal('b'),
                     Literal('a')).eval(env) == 'b'
        assert Apply(Reference("count-selected"),
                     Literal(u'a bb 日本')).eval(env) == 3
        assert Apply(Reference("sha1"), Literal(u'a bb 日本')
                    ).eval(env) == 'e25a54025417b06d88d40baa8c71f6eee9c07fb1'
        assert Apply(Reference("sha1"), Literal(b'2015')
                    ).eval(env) == '9cdda67ded3f25811728276cefa76b80913b4c54'
        assert Apply(Reference("sha1"), Literal(2015)
                    ).eval(env) == '9cdda67ded3f25811728276cefa76b80913b4c54'

    def test_or(self):
        env = BuiltInEnv()
        assert Apply(Reference("or"), Literal(None), Literal(2)).eval(env) == 2

        laziness_iterator = RepeatableIterator(
            lambda: (i if i < 1 else die('Not lazy enough') for i in range(2))
        )
        assert Apply(Reference("or"), Literal(1),
                     Literal(laziness_iterator)).eval(env) == 1
        assert Apply(Reference("or"), Literal(''),
                     Literal(laziness_iterator)).eval(env) == ''
        assert Apply(Reference("or"), Literal(0),
                     Literal(laziness_iterator)).eval(env) == 0
        with pytest.raises(LazinessException):
            Apply(Reference("or"), Literal(None),
                  Literal(laziness_iterator)).eval(env)

        env = env | JsonPathEnv({'a': {'c': 'c val'}})
        assert Apply(Reference("or"), Reference('a.b'),
                     Reference('a.c')).eval(env) == 'c val'
        assert Apply(Reference("or"), Reference('a.b'),
                     Reference('a.d')).eval(env) is None

        env = env.replace({'a': [], 'b': [1, 2], 'c': 2})
        self.check_case(
            Apply(Reference("or"), Reference('a.[*]'),
                  Reference('b')).eval(env), [1, 2]
        )
        self.check_case(
            Apply(Reference("or"), Reference('b.[*]'),
                  Reference('c')).eval(env), [1, 2]
        )
        self.check_case(
            Apply(Reference("or"), Reference('a.[*]'),
                  Reference('$')).eval(env), {
                      'a': [],
                      'b': [1, 2],
                      'c': 2,
                      'id': '$'
                  }
        )

    def test_attachment_url(self):
        env = BuiltInEnv({'commcarehq_base_url': 'https://www.commcarehq.org'}
                        ) | JsonPathEnv({
                            'id': '123',
                            'domain': 'd1',
                            'photo': 'a.jpg'
                        })
        expected = 'https://www.commcarehq.org/a/d1/api/form/attachment/123/a.jpg'
        assert Apply(Reference('attachment_url'),
                     Reference('photo')).eval(env) == expected

    def test_attachment_url_repeat(self):
        env = BuiltInEnv({'commcarehq_base_url': 'https://www.commcarehq.org'}
                        ) | JsonPathEnv({
                            'id': '123',
                            'domain': 'd1',
                            'repeat': [{
                                'photo': 'a.jpg'
                            }, {
                                'photo': 'b.jpg'
                            }]
                        })
        expected = [
            'https://www.commcarehq.org/a/d1/api/form/attachment/123/a.jpg',
            'https://www.commcarehq.org/a/d1/api/form/attachment/123/b.jpg',
        ]
        result = unwrap_val(
            Map(
                source=Reference('repeat.[*]'),
                body=Apply(Reference('attachment_url'), Reference('photo'))
            ).eval(env)
        )
        assert result == expected

    def test_form_url(self):
        env = BuiltInEnv({'commcarehq_base_url': 'https://www.commcarehq.org'}
                        ) | JsonPathEnv({
                            'id': '123',
                            'domain': 'd1'
                        })
        expected = 'https://www.commcarehq.org/a/d1/reports/form_data/123/'
        assert Apply(Reference('form_url'),
                     Reference('id')).eval(env) == expected

    def test_case_url(self):
        env = BuiltInEnv({'commcarehq_base_url': 'https://www.commcarehq.org'}
                        ) | JsonPathEnv({
                            'id': '123',
                            'domain': 'd1'
                        })
        expected = 'https://www.commcarehq.org/a/d1/reports/case_data/123/'
        assert Apply(Reference('case_url'),
                     Reference('id')).eval(env) == expected

    def test_unique(self):
        env = BuiltInEnv() | JsonPathEnv({
            "list": [{
                "a": 1
            }, {
                "a": 2
            }, {
                "a": 3
            }, {
                "a": 2
            }]
        })
        assert Apply(Reference('unique'),
                     Reference('list[*].a')).eval(env) == [1, 2, 3]

    def test_template(self):
        env = BuiltInEnv() | JsonPathEnv({'a': '1', 'b': '2'})
        assert Apply(
            Reference('template'), Literal('{}.{}'), Reference('a'),
            Reference('b')
        ).eval(env) == '1.2'

    def test_substr(self):
        env = BuiltInEnv({
            'single_byte_chars': u'abcdefghijklmnopqrstuvwxyz',
            'multi_byte_chars': u'αβγδεζηθικλμνξοπρςστυφχψω',
            'an_integer': 123456
        })
        assert Apply(
            Reference('substr'), Reference('single_byte_chars'), Literal(-4),
            Literal(30)
        ).eval(env) == None
        assert Apply(
            Reference('substr'), Reference('single_byte_chars'), Literal(0),
            Literal(26)
        ).eval(env) == u'abcdefghijklmnopqrstuvwxyz'
        assert Apply(
            Reference('substr'), Reference('single_byte_chars'), Literal(10),
            Literal(16)
        ).eval(env) == u'klmnop'
        assert Apply(
            Reference('substr'), Reference('single_byte_chars'), Literal(13),
            Literal(14)
        ).eval(env) == u'n'
        assert Apply(
            Reference('substr'), Reference('single_byte_chars'), Literal(13),
            Literal(13)
        ).eval(env) == u''
        assert Apply(
            Reference('substr'), Reference('single_byte_chars'), Literal(14),
            Literal(13)
        ).eval(env) == u''
        assert Apply(
            Reference('substr'), Reference('single_byte_chars'), Literal(5),
            Literal(-1)
        ).eval(env) == None

        assert Apply(
            Reference('substr'), Reference('multi_byte_chars'), Literal(-4),
            Literal(30)
        ).eval(env) == None
        assert Apply(
            Reference('substr'), Reference('multi_byte_chars'), Literal(0),
            Literal(25)
        ).eval(env) == u'αβγδεζηθικλμνξοπρςστυφχψω'
        assert Apply(
            Reference('substr'), Reference('multi_byte_chars'), Literal(10),
            Literal(15)
        ).eval(env) == u'λμνξο'
        assert Apply(
            Reference('substr'), Reference('multi_byte_chars'), Literal(13),
            Literal(14)
        ).eval(env) == u'ξ'
        assert Apply(
            Reference('substr'), Reference('multi_byte_chars'), Literal(13),
            Literal(12)
        ).eval(env) == u''
        assert Apply(
            Reference('substr'), Reference('multi_byte_chars'), Literal(14),
            Literal(13)
        ).eval(env) == u''
        assert Apply(
            Reference('substr'), Reference('multi_byte_chars'), Literal(5),
            Literal(-1)
        ).eval(env) == None

        assert Apply(
            Reference('substr'), Reference('an_integer'), Literal(-1),
            Literal(3)
        ).eval(env) == None
        assert Apply(
            Reference('substr'), Reference('an_integer'), Literal(0),
            Literal(6)
        ).eval(env) == u'123456'
        assert Apply(
            Reference('substr'), Reference('an_integer'), Literal(2),
            Literal(4)
        ).eval(env) == u'34'
        assert Apply(
            Reference('substr'), Reference('an_integer'), Literal(4),
            Literal(2)
        ).eval(env) == u''
        assert Apply(
            Reference('substr'), Reference('an_integer'), Literal(5),
            Literal(-1)
        ).eval(env) == None

    def test_map(self):
        env = BuiltInEnv() | DictEnv({})

        laziness_iterator = RepeatableIterator(
            lambda: ({
                'a': i
            } if i < 5 else die('Not lazy enough') for i in range(12))
        )

        assert list(
            Map(
                source=Literal([{
                    'a': 1
                }, {
                    'a': 2
                }, {
                    'a': 3
                }]),
                body=Literal(1)
            ).eval(env)
        ) == [1, 1, 1]
        assert list(
            Map(
                source=Literal([{
                    'a': 1
                }, {
                    'a': 2
                }, {
                    'a': 3
                }]),
                body=Reference('a')
            ).eval(env)
        ) == [1, 2, 3]

        assert list(
            islice(
                Map(source=Literal(laziness_iterator),
                    body=Reference('a')).eval(env), 5
            )
        ) == [0, 1, 2, 3, 4]

        try:
            list(
                Map(source=Literal(laziness_iterator),
                    body=Reference('a')).eval(env)
            )
            raise Exception('Should have failed')
        except LazinessException:
            pass

    def test_flatmap(self):
        env = BuiltInEnv() | DictEnv({})

        laziness_iterator = RepeatableIterator(
            lambda: ({
                'a': range(i)
            } if i < 4 else die('Not lazy enough') for i in range(12))
        )

        assert list(
            FlatMap(
                source=Literal([{
                    'a': [1]
                }, {
                    'a': 'foo'
                }, {
                    'a': [3, 4]
                }]),
                body=Literal([1, 2, 3])
            ).eval(env)
        ) == [1, 2, 3, 1, 2, 3, 1, 2, 3]
        assert list(
            FlatMap(
                source=Literal([{
                    'a': [1]
                }, {
                    'a': [2]
                }, {
                    'a': [3, 4]
                }]),
                body=Reference('a')
            ).eval(env)
        ) == [1, 2, 3, 4]

        assert list(
            islice(
                FlatMap(
                    source=Literal(laziness_iterator), body=Reference('a')
                ).eval(env), 6
            )
        ) == [0, 0, 1, 0, 1, 2]

        try:
            list(
                FlatMap(
                    source=Literal(laziness_iterator), body=Reference('a')
                ).eval(env)
            )
            raise Exception('Should have failed')
        except LazinessException:
            pass

    def _setup_emit_test(self, emitter_env):
        env = BuiltInEnv() | JsonPathEnv({
            'foo': {
                'baz': 3,
                'bar': True,
                'boo': None
            }
        }) | emitter_env
        Emit(
            table='Foo',
            headings=[Literal('foo')],
            source=List([
                List([
                    Reference('foo.baz'),
                    Reference('foo.bar'),
                    Reference('foo.foo'),
                    Reference('foo.boo')
                ])
            ]),
            missing_value='---'
        ).eval(env)

    def test_emit(self):
        writer = JValueTableWriter()
        self._setup_emit_test(EmitterEnv(writer))
        assert list(writer.tables['Foo'].rows) == [[3, True, '---', None]]

    def test_emit_generator(self):

        class TestWriter(JValueTableWriter):

            def write_table(self, table):
                self.tables[table.name] = table

        writer = TestWriter()
        self._setup_emit_test(EmitterEnv(writer))
        assert isinstance(
            writer.tables['Foo'].rows, (map, filter, types.GeneratorType)
        )

    def test_emit_env_generator(self):

        class TestEmitterEnv(EmitterEnv):

            def emit_table(self, table_spec):
                self.table = table_spec

        env = TestEmitterEnv(JValueTableWriter())
        self._setup_emit_test(env)
        assert isinstance(env.table.rows, (map, filter, types.GeneratorType))

    def test_emit_multi_same_query(self):
        """
        Test that we can emit multiple tables from the same set of
        source data. This is useful if you need to generate multiple
        tables from the same datasource.
        """
        writer = JValueTableWriter()
        env = BuiltInEnv() | JsonPathEnv() | EmitterEnv(writer)

        result = Map(
            source=Literal([
                {
                    'foo': {
                        'baz': 3,
                        'bar': True,
                        'boo': None
                    }
                },
                {
                    'foo': {
                        'baz': 4,
                        'bar': False,
                        'boo': 1
                    }
                },
            ]),
            body=List([
                Emit(
                    table='FooBaz',
                    headings=[Literal('foo')],
                    source=List([List([Reference('foo.baz')])]),
                ),
                Emit(
                    table='FooBar',
                    headings=[Literal('foo')],
                    source=List([List([Reference('foo.bar')])]),
                )
            ]),
        ).eval(env)

        # evaluate result
        list(result)
        assert 2 == len(writer.tables)
        assert writer.tables['FooBaz'].rows == [[3], [4]]
        assert writer.tables['FooBar'].rows == [[True], [False]]

    def test_emit_mutli_different_query(self):
        """
        Test that we can emit multiple tables from the same set of
        source data even if the emitted table have different 'root doc'
        expressions.

        Example use case could be emitting cases and case actions, or
        form data and repeats.
        """
        writer = JValueTableWriter()
        env = BuiltInEnv() | JsonPathEnv() | EmitterEnv(writer)
        result = Filter(  # the filter here is to prevent accumulating a `[None]` value for each doc
            predicate=Apply(
                Reference("filter_empty"),
                Reference("$")
            ),
            source=Map(
                # in practice `source` would be and api query such as
                # Apply(Reference('api_data'), Literal('case'), Literal({'type': 'case_type'}))
                source=Literal([
                    {'id': 1, 'foo': {'baz': 3, 'bar': True, 'boo': None}, 'actions': [{'a': 3}, {'a': 4}]},
                    {'id': 2, 'foo': {'baz': 4, 'bar': False, 'boo': 1}, 'actions': [{'a': 5}, {'a': 6}]},
                ]),
                body=List([
                    Emit(
                        table="t1",
                        headings=[Literal("id")],
                        source=Map(
                            source=Reference("`this`"),
                            body=List([
                                Reference("id"),
                            ]),
                        )
                    ),
                    Emit(
                        table="t2",
                        headings=[Literal("id"), Literal("a")],
                        source=Map(
                            source=Reference("actions[*]"),
                            body=List([
                                Reference("$.id"),
                                Reference("a")
                            ]),
                        )
                    )
                ])
            )
        ).eval(env)

        # evaluate result
        list(result)
        assert writer.tables['t1'].rows == [['1'], ['2']]
        assert writer.tables['t2'].rows == [['1', 3], ['1', 4], ['2', 5],
                                            ['2', 6]]

    def test_from_jvalue(self):
        assert MiniLinq.from_jvalue({"Ref": "form.log_subreport"}
                                   ) == Reference("form.log_subreport")
        assert (
            MiniLinq.from_jvalue({
                "Apply": {
                    "fn": {
                        "Ref": "len"
                    },
                    "args": [{
                        "Ref": "form.log_subreport"
                    }]
                }
            }) == Apply(Reference("len"), Reference("form.log_subreport"))
        )
        assert MiniLinq.from_jvalue([{
            "Ref": "form.log_subreport"
        }]) == [Reference("form.log_subreport")]

    def test_filter(self):
        env = BuiltInEnv() | DictEnv({})
        named = [{'n': n} for n in range(1, 5)]
        assert list(
            Filter(
                Literal(named),
                Apply(Reference('>'), Reference('n'), Literal(2))
            ).eval(env)
        ) == [{
            'n': 3
        }, {
            'n': 4
        }]
        assert list(
            Filter(
                Literal([1, 2, 3, 4]),
                Apply(Reference('>'), Reference('n'), Literal(2)), 'n'
            ).eval(env)
        ) == [3, 4]

    def test_emit_table_unwrap_dicts(self):
        writer = JValueTableWriter()
        env = EmitterEnv(writer)
        env.emit_table(
            TableSpec(
                **{
                    'name':
                        't1',
                    'headings': ['a'],
                    'rows': [
                        ['hi'],
                        [{
                            '#text': 'test_text',
                            '@case_type': 'person',
                            '@relationship': 'child',
                            'id': 'nothing'
                        }],
                        [{
                            '@case_type': '',
                            '@relationship': 'child',
                            'id': 'some_id'
                        }],
                        [{
                            't': 123
                        }],
                    ]
                }
            )
        )

        writer.tables['t1'].rows = [['hi'], ['test_text'], [''], [{'t': 123}]]
