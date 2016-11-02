import unittest
from itertools import *
from six.moves import map, xrange

from jsonpath_rw import jsonpath

from commcare_export.minilinq import *
from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.env import *

class LazinessException(Exception): pass
def die(msg): raise LazinessException(msg) # Hack: since "raise" is a statement not an expression, need a funcall wrapping it

class TestMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def check_case(self, val, expected):
        if isinstance(expected, list):
            assert [datum.value if isinstance(datum, jsonpath.DatumInContext) else datum for datum in val] == expected

    def test_eval_literal(self):
        env = BuiltInEnv()
        assert Literal("foo").eval(env) == "foo"
        assert Literal(2).eval(env) == 2
        assert Literal({'foo': 'baz'}).eval(env) == {'foo': 'baz'}

    def test_eval_reference(self):
        env = BuiltInEnv()
        assert Reference("foo").eval(DictEnv({'foo': 2})) == 2
        self.check_case(Reference("foo[*]").eval(JsonPathEnv({'foo': [2]})), [2])
        self.check_case(Reference("foo[*]").eval(JsonPathEnv({'foo': xrange(0, 1)})), [0]) # Should work the same w/ iterators as with lists

        # Should be able to get back out to the root, as the JsonPathEnv actually passes the full datum around
        self.check_case(Reference("foo.$.baz").eval(JsonPathEnv({'foo': [2], 'baz': 3})), [3])

    def test_eval_auto_id_reference(self):
        "Test that we have turned on the jsonpath_rw.jsonpath.auto_id field properly"
        env = BuiltInEnv()

        self.check_case(Reference("foo.id").eval(JsonPathEnv({'foo': [2]})), ['foo'])

        # When auto id is on, this always becomes a string. Sorry!
        self.check_case(Reference("foo.id").eval(JsonPathEnv({'foo': {'id': 2}})), ['2'])

    def test_eval_collapsed_list(self):
        """
        Special case to handle XML -> JSON conversion where there just happened to be a single value at save time
        """
        env = BuiltInEnv()
        self.check_case(Reference("foo[*]").eval(JsonPathEnv({'foo': 2})), [2])
        assert Apply(Reference("*"), Literal(2), Literal(3)).eval(env) == 6
        assert Apply(Reference(">"), Literal(56), Literal(23.5)).eval(env) == True
        assert Apply(Reference("len"), Literal([1, 2, 3])).eval(env) == 3
        assert Apply(Reference("bool"), Literal('a')).eval(env) == True
        assert Apply(Reference("bool"), Literal('')).eval(env) == False
        assert Apply(Reference("str2bool"), Literal('true')).eval(env) == True
        assert Apply(Reference("str2bool"), Literal('t')).eval(env) == True
        assert Apply(Reference("str2bool"), Literal('1')).eval(env) == True
        assert Apply(Reference("str2bool"), Literal('0')).eval(env) == False
        assert Apply(Reference("str2bool"), Literal('false')).eval(env) == False
        assert Apply(Reference("str2num"), Literal('10')).eval(env) == 10
        assert Apply(Reference("str2num"), Literal('10.56')).eval(env) == 10.56
        assert Apply(Reference("str2date"), Literal('2015-01-01')).eval(env) == datetime(2015, 1, 1)
        assert Apply(Reference("str2date"), Literal('2015-01-01T18:32:57')).eval(env) == datetime(2015, 1, 1, 18, 32, 57)
        assert Apply(Reference("str2date"), Literal('2015-01-01T18:32:57.001200')).eval(env) == datetime(2015, 1, 1, 18, 32, 57)
        assert Apply(Reference("str2date"), Literal('2015-01-01T18:32:57.001200Z')).eval(env) == datetime(2015, 1, 1, 18, 32, 57)
        assert Apply(Reference("selected-at"), Literal('a b c'), Literal('1')).eval(env) == 'b'
        assert Apply(Reference("selected-at"), Literal('a b c'), Literal('-1')).eval(env) == 'c'
        assert Apply(Reference("selected-at"), Literal('a b c'), Literal('5')).eval(env) is None
        assert Apply(Reference("selected"), Literal('a b c'), Literal('b')).eval(env) is True
        assert Apply(Reference("selected"), Literal('a b c'), Literal('d')).eval(env) is False
        assert Apply(Reference("selected"), Literal('a bb c'), Literal('b')).eval(env) is False

    def test_map(self):
        env = BuiltInEnv() | DictEnv({})

        laziness_iterator = RepeatableIterator(lambda: ({'a':i} if i < 5 else die('Not lazy enough') for i in range(12)))
        
        assert list(Map(source=Literal([{'a':1}, {'a':2}, {'a':3}]), body=Literal(1)).eval(env)) == [1, 1, 1]
        assert list(Map(source=Literal([{'a':1}, {'a':2}, {'a':3}]), body=Reference('a')).eval(env)) == [1, 2, 3]

        assert list(islice(Map(source=Literal(laziness_iterator), body=Reference('a')).eval(env), 5)) == [0, 1, 2, 3, 4]

        try:
            list(Map(source=Literal(laziness_iterator), body=Reference('a')).eval(env))
            raise Exception('Should have failed')
        except LazinessException:
            pass

    def test_flatmap(self):
        env = BuiltInEnv() | DictEnv({})

        laziness_iterator = RepeatableIterator(lambda: ({'a':range(i)} if i < 4 else die('Not lazy enough') for i in range(12)))

        assert list(FlatMap(source=Literal([{'a':[1]}, {'a':'foo'}, {'a':[3, 4]}]), body=Literal([1, 2, 3])).eval(env)) == [1, 2, 3, 1, 2, 3, 1, 2, 3]
        assert list(FlatMap(source=Literal([{'a':[1]}, {'a':[2]}, {'a':[3, 4]}]), body=Reference('a')).eval(env)) == [1, 2, 3, 4]

        assert list(islice(FlatMap(source=Literal(laziness_iterator), body=Reference('a')).eval(env), 6)) == [0,
                                                                                                              0, 1,
                                                                                                              0, 1, 2]

        try:
            list(FlatMap(source=Literal(laziness_iterator), body=Reference('a')).eval(env))
            raise Exception('Should have failed')
        except LazinessException:
            pass

    def test_emit(self):
        env = BuiltInEnv() | JsonPathEnv({'foo': {'baz': 3, 'bar': True}})
        Emit(table='Foo',
             headings=[Literal('foo')],
             source=List([
                 List([ Reference('foo.baz'), Reference('foo.bar') ])
             ])).eval(env)

        assert list(list(env.emitted_tables())[0]['rows']) == [[3, True]]

    def test_from_jvalue(self):
        assert MiniLinq.from_jvalue({"Ref": "form.log_subreport"}) == Reference("form.log_subreport")
        assert (MiniLinq.from_jvalue({"Apply": {"fn":   {"Ref":"len"}, "args": [{"Ref": "form.log_subreport"}]}})
                == Apply(Reference("len"), Reference("form.log_subreport")))
        assert MiniLinq.from_jvalue([{"Ref": "form.log_subreport"}]) == [Reference("form.log_subreport")]

    def test_filter(self):
        env = BuiltInEnv() | DictEnv({})
        named = [{'n': n} for n in range(1, 5)]
        assert list(Filter(Literal(named), Apply(Reference('>'), Reference('n'), Literal(2))).eval(env)) == [{'n': 3}, {'n': 4}]
        assert list(Filter(Literal([1, 2, 3, 4]), Apply(Reference('>'), Reference('n'), Literal(2)), 'n').eval(env)) == [3, 4]
