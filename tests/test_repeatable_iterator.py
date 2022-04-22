import unittest
from itertools import *

from commcare_export.repeatable_iterator import RepeatableIterator


class TestRepeatableIterator(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_iteration(self):

        class LazinessException(Exception):
            pass

        def test1():
            for i in range(1, 100):
                yield i

        def test2():
            for i in range(1, 100):
                if i > 10:
                    raise LazinessException('Not lazy enough')
                yield i

        # First make sure that we've properly set up a situation that
        # fails without RepeatableIterator
        iterator = test1()
        assert list(iterator) == list(range(1, 100))
        assert list(iterator) == []

        # Now test that the RepeatableIterator restores functionality
        iterator = RepeatableIterator(test1)
        assert list(iterator) == list(range(1, 100))
        assert list(iterator) == list(range(1, 100))
        assert bool(iterator) is True

        iterator = RepeatableIterator(lambda: (i for i in []))
        assert bool(iterator) is False

        # Ensure that laziness is maintained
        iterator = RepeatableIterator(test2)
        assert list(islice(iterator, 5)) == list(range(1, 6))

        try:
            list(islice(iterator, 15))
            raise Exception('Should have failed')
        except LazinessException:
            pass
