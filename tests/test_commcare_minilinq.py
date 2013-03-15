import unittest
import simplejson
import urllib

from commcare_export.minilinq import *
from commcare_export.env import *
from commcare_export.commcare_hq_client import MockCommCareHqClient
from commcare_export.commcare_minilinq import *

class TestCommCareMiniLinq(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_eval(self):
        client = MockCommCareHqClient({
            'form': {
                urllib.urlencode({'_search': simplejson.dumps({"filter":"test1"})}): [1, 2, 3]
            }
        })

        env = BuiltInEnv() | CommCareHqEnv(client) | JsonPathEnv({}) # {'form': api_client.iterate('form')})

        assert Apply(Reference('api_data'),
                     Literal('form'),
                     Literal({"filter": 'test1'})).eval(env) == [1, 2, 3]
