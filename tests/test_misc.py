import hashlib
import struct
import tempfile
import unittest

from commcare_export import misc
from commcare_export.repeatable_iterator import RepeatableIterator
from jsonpath_ng import jsonpath


class TestDigestFile(unittest.TestCase):

    def check_digest(self, contents):
        with tempfile.NamedTemporaryFile(
            prefix='commcare-export-test-', mode='wb'
        ) as file:
            file.write(contents)
            file.flush()
            file_digest = misc.digest_file(file.name)

        # Make sure the chunking does not mess with stuff
        assert file_digest == hashlib.md5(contents).hexdigest()

    def test_digest_file_ascii(self):
        self.check_digest('Hello'.encode('utf-8'))

    def test_digest_file_long(self):
        self.check_digest(('Hello' * 100000).encode('utf-8'))

    def test_digest_file_utf8(self):
        self.check_digest('Miércoles'.encode('utf-8'))

    def test_digest_file_binary(self):
        self.check_digest(struct.pack('III'.encode('ascii'), 1, 2, 3))


class TestUnwrap(unittest.TestCase):
    """
    Tests for the @unwrap decorator, which unwraps RepeatableIterators,
    single-element lists, and jsonpath DatumInContext objects before
    passing them to the decorated function.
    """

    def test_unwrap_first_argument(self):
        @misc.unwrap('val')
        def process_value(val, multiplier):
            return val * multiplier

        ri = RepeatableIterator(lambda: iter([42]))
        self.assertEqual(process_value(ri, 2), 84)

        self.assertEqual(process_value([10], 3), 30)

        self.assertEqual(process_value(5, 4), 20)

    def test_unwrap_middle_argument(self):
        @misc.unwrap('target')
        def process_middle(prefix, target, suffix):
            return f"{prefix}_{target}_{suffix}"

        self.assertEqual(process_middle("a", ["b"], "c"), "a_b_c")

        ri = RepeatableIterator(lambda: iter(["x"]))
        self.assertEqual(process_middle("start", ri, "end"), "start_x_end")

    def test_unwrap_last_argument(self):
        @misc.unwrap('data')
        def process_last(operation, multiplier, data):
            if operation == "multiply":
                return data * multiplier
            return data

        ri = RepeatableIterator(lambda: iter([7]))
        self.assertEqual(process_last("multiply", 3, ri), 21)

    def test_unwrap_repeatable_iterator(self):
        @misc.unwrap('val')
        def get_value(val):
            return val

        ri_single = RepeatableIterator(lambda: iter([42]))
        self.assertEqual(get_value(ri_single), 42)

        ri_multi = RepeatableIterator(lambda: iter([1, 2, 3]))
        self.assertEqual(get_value(ri_multi), [1, 2, 3])

        ri_empty = RepeatableIterator(lambda: iter([]))
        self.assertEqual(get_value(ri_empty), [])

    def test_unwrap_single_element_list(self):
        @misc.unwrap('val')
        def get_value(val):
            return val

        self.assertEqual(get_value([42]), 42)
        self.assertEqual(get_value(["text"]), "text")
        self.assertEqual(get_value([{"key": "value"}]), {"key": "value"})

    def test_unwrap_multi_element_list(self):
        @misc.unwrap('val')
        def get_value(val):
            return val

        result = get_value([[1], [2], [3]])
        self.assertEqual(result, [1, 2, 3])

    def test_unwrap_jsonpath_datum(self):
        @misc.unwrap('val')
        def get_value(val):
            return val

        datum = jsonpath.DatumInContext(value="extracted_value", path=None, context=None)
        self.assertEqual(get_value(datum), "extracted_value")

        datum_nested = jsonpath.DatumInContext(value=42, path=None, context=None)
        self.assertEqual(get_value([datum_nested]), 42)

    def test_unwrap_nested_structures(self):
        @misc.unwrap('val')
        def get_value(val):
            return val

        ri = RepeatableIterator(lambda: iter([[10]]))
        self.assertEqual(get_value(ri), [10])

        datum = jsonpath.DatumInContext(value="nested", path=None, context=None)
        self.assertEqual(get_value([datum]), "nested")

        ri_simple = RepeatableIterator(lambda: iter([42]))
        self.assertEqual(get_value(ri_simple), 42)

    def test_unwrap_preserves_non_wrappable_values(self):
        @misc.unwrap('val')
        def get_value(val):
            return val

        self.assertEqual(get_value(42), 42)
        self.assertEqual(get_value("text"), "text")
        self.assertEqual(get_value(None), None)
        self.assertEqual(get_value({"key": "value"}), {"key": "value"})

        self.assertEqual(get_value([1, 2, 3]), [1, 2, 3])

    def test_unwrap_with_methods(self):
        class Processor:
            def __init__(self, base):
                self.base = base

            @misc.unwrap('val')
            def process(self, val):
                return self.base + val

        proc = Processor(100)
        self.assertEqual(proc.process([10]), 110)

        ri = RepeatableIterator(lambda: iter([5]))
        self.assertEqual(proc.process(ri), 105)
