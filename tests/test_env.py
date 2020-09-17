import doctest

from commcare_export.env import hex2uuid


class TestHex2UUID:
    def test_invalid_hex_int(self):
        assert hex2uuid(0xf00) is None

    def test_invalid_hex_str(self):
        assert hex2uuid('f00') is None

    def test_uuid(self):
        assert hex2uuid('00a3e019-4ce1-4587-94c5-0971dee2de22') \
               == '00a3e019-4ce1-4587-94c5-0971dee2de22'


def test_doctests():
    import commcare_export.env

    results = doctest.testmod(commcare_export.env)
    assert results.failed == 0
