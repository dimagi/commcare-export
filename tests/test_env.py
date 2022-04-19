import doctest

import commcare_export.env


def test_doctests():
    results = doctest.testmod(commcare_export.env)
    assert results.failed == 0
