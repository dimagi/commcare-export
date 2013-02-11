import unittest

from commcare_export.minilinq import *
from commcare_export.env import *

class TestMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_eval(self):
        env = BuiltInEnv()
        
        assert Literal("foo").eval(env) == "foo"
        assert Literal(2).eval(env) == 2
        assert Apply(Reference("*"), Literal(2), Literal(3)).eval(env) == 6
        assert Apply(Reference(">"), Literal(56), Literal(23.5)).eval(env) == True
        assert Apply(Reference("len"), Literal([1, 2, 3])).eval(env) == 3

    def test_from_jvalue(self):

        assert MiniLinq.from_jvalue({"Ref": "form.log_subreport"}) == Reference("form.log_subreport")
        assert (MiniLinq.from_jvalue({"Apply": {"fn":   {"Ref":"len"}, "args": [{"Ref": "form.log_subreport"}]}})
                == Apply(Reference("len"), Reference("form.log_subreport")))
