import pytest

from commcare_export.version import parse_version


@pytest.mark.parametrize(
    "input,output",
    [
        ("1.2.3", "1.2.3"),
        ("1.2", "1.2"),
        ("0.1.5-3", "0.1.5.dev3"),
        ("0.1.5-3-g1234567", "0.1.5.dev3"),
        ("0.1.5-4-g1234567-dirty", "0.1.5.dev4"),
        ("0.1.5-15-g1234567-dirty-123", "0.1.5.dev15"),
        ("a.b.c", "a.b.c"),
    ]
)
def test_parse_version(input, output):
    assert parse_version(input) == output
