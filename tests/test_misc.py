import doctest
import hashlib
import struct
import tempfile
import unittest

import pytest

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


class TestUnwrap:
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
        assert process_value(ri, 2) == 84
        assert process_value([10], 3) == 30
        assert process_value(5, 4) == 20

    def test_unwrap_middle_argument(self):
        @misc.unwrap('target')
        def process_middle(prefix, target, suffix):
            return f"{prefix}_{target}_{suffix}"

        assert process_middle("a", ["b"], "c") == "a_b_c"

        ri = RepeatableIterator(lambda: iter(["x"]))
        assert process_middle("start", ri, "end") == "start_x_end"

    def test_unwrap_last_argument(self):
        @misc.unwrap('data')
        def process_last(operation, multiplier, data):
            assert operation == "multiply"
            return data * multiplier

        ri = RepeatableIterator(lambda: iter([7]))
        assert process_last("multiply", 3, ri) == 21

    @pytest.mark.parametrize("iterator_data,expected", [
        ([42], 42),
        ([1, 2, 3], [1, 2, 3]),
        ([], []),
    ])
    def test_unwrap_repeatable_iterator(self, iterator_data, expected):
        @misc.unwrap('val')
        def get_value(val):
            return val

        ri = RepeatableIterator(lambda: iter(iterator_data))
        assert get_value(ri) == expected

    @pytest.mark.parametrize("input_val,expected", [
        ([42], 42),
        (["text"], "text"),
        ([{"key": "value"}], {"key": "value"}),
    ])
    def test_unwrap_single_element_list(self, input_val, expected):
        @misc.unwrap('val')
        def get_value(val):
            return val

        assert get_value(input_val) == expected

    def test_unwrap_multi_element_list(self):
        @misc.unwrap('val')
        def get_value(val):
            return val

        result = get_value([[1], [2], [3]])
        assert result == [1, 2, 3]

    @pytest.mark.parametrize("value,wrap_in_list", [
        ("extracted_value", False),
        (42, True),
        ("nested", True),
    ])
    def test_unwrap_jsonpath_datum(self, value, wrap_in_list):
        @misc.unwrap('val')
        def get_value(val):
            return val

        datum = jsonpath.DatumInContext(value=value, path=None, context=None)
        input_val = [datum] if wrap_in_list else datum
        assert get_value(input_val) == value

    @pytest.mark.parametrize("iterator_data,expected", [
        ([[10]], [10]),
    ])
    def test_unwrap_nested_structures(self, iterator_data, expected):
        @misc.unwrap('val')
        def get_value(val):
            return val

        ri = RepeatableIterator(lambda: iter(iterator_data))
        assert get_value(ri) == expected

    @pytest.mark.parametrize("input_val,expected", [
        (42, 42),
        ("text", "text"),
        (None, None),
        ({"key": "value"}, {"key": "value"}),
        ([1, 2, 3], [1, 2, 3]),
    ])
    def test_unwrap_preserves_non_wrappable_values(self, input_val, expected):
        @misc.unwrap('val')
        def get_value(val):
            return val

        assert get_value(input_val) == expected

    def test_unwrap_with_methods(self):
        class Processor:
            def __init__(self, base):
                self.base = base

            @misc.unwrap('val')
            def process(self, val):
                return self.base + val

        proc = Processor(100)
        assert proc.process([10]) == 110

        ri = RepeatableIterator(lambda: iter([5]))
        assert proc.process(ri) == 105


def test_doctests():
    results = doctest.testmod(misc)
    assert results.failed == 0
