import unittest
from itertools import *

from commcare_export.minilinq import *
from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.env import *

class LazinessException(Exception): pass
def die(msg): raise LazinessException(msg) # Hack: since "raise" is a statement not an expression, need a funcall wrapping it

class TestMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_eval_literal(self):
        env = BuiltInEnv()
        assert Literal("foo").eval(env) == "foo"
        assert Literal(2).eval(env) == 2
        assert Literal({'foo': 'baz'}).eval(env) == {'foo': 'baz'}

    def test_eval_reference(self):
        env = BuiltInEnv()
        assert Reference("foo").eval(DictEnv({'foo': 2})) == 2
        assert list(Reference("foo[*]").eval(JsonPathEnv({'foo': [2]}))) == [2]
        assert list(Reference("foo[*]").eval(JsonPathEnv({'foo': xrange(0, 1)}))) == [0] # Should work the same w/ iterators as with lists

    def test_eval_auto_id_reference(self):
        "Test that we have turned on the jsonpath_rw.jsonpath.auto_id field properly"
        env = BuiltInEnv()
        assert list(Reference("foo.id").eval(JsonPathEnv({'foo': [2]}))) == ['foo']
        assert list(Reference("foo.id").eval(JsonPathEnv({'foo': {'id': 2}}))) == [2]

    def test_eval_collapsed_list(self):
        """
        Special case to handle XML -> JSON conversion where there just happened to be a single value at save time
        """
        env = BuiltInEnv()
        assert list(Reference("foo[*]").eval(JsonPathEnv({'foo': 2}))) == [2]
        assert Apply(Reference("*"), Literal(2), Literal(3)).eval(env) == 6
        assert Apply(Reference(">"), Literal(56), Literal(23.5)).eval(env) == True
        assert Apply(Reference("len"), Literal([1, 2, 3])).eval(env) == 3

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

    def test_from_jvalue(self):
        assert MiniLinq.from_jvalue({"Ref": "form.log_subreport"}) == Reference("form.log_subreport")
        assert (MiniLinq.from_jvalue({"Apply": {"fn":   {"Ref":"len"}, "args": [{"Ref": "form.log_subreport"}]}})
                == Apply(Reference("len"), Reference("form.log_subreport")))
