import unittest

from commcare_export.repeatable_iterator import RepeatableIterator

class TestRepeatableIterator(unittest.TestCase):

    @classmethod
    def setup_class(cls):
        pass

    def test_iteration(self):

        def test1(): 
            for i in range(1, 100): 
                yield i

        # First make sure that we've properly set up a situation that fails
        # without RepeatableIterator
        iterator = test1()
        assert list(iterator) == range(1, 100)
        assert list(iterator) == []
        
        # Now test that the RepeatableIterator restores functionality
        iterator = RepeatableIterator(test1)
        assert list(iterator) == range(1, 100)
        assert list(iterator) == range(1, 100)
