import pytest
from commcare_export.specs import TableSpec


class TestTableSpec:

    def test_basic_instantiation(self):
        table = TableSpec('test', ['col1', 'col2'], iter([['a', 'b'], ['c', 'd']]))

        assert table.name == 'test'
        assert table.headings == ['col1', 'col2']
        assert list(table.rows) == [['a', 'b'], ['c', 'd']]
        assert table.data_types == []

    def test_keyword_instantiation(self):
        table = TableSpec(
            name='test_table',
            headings=['col1', 'col2'],
            rows=iter([['x', 'y']]),
            data_types=['text', 'integer']
        )

        assert table.name == 'test_table'
        assert table.headings == ['col1', 'col2']
        assert list(table.rows) == [['x', 'y']]
        assert table.data_types == ['text', 'integer']

    def test_unpacking_instantiation(self):
        table_data = {
            'name': 'unpacked_table',
            'headings': ['id', 'value'],
            'rows': iter([[1, 'test'], [2, 'data']]),
            'data_types': ['integer', 'text']
        }

        table = TableSpec(**table_data)

        assert table.name == 'unpacked_table'
        assert table.headings == ['id', 'value']
        assert list(table.rows) == [[1, 'test'], [2, 'data']]
        assert table.data_types == ['integer', 'text']

    def test_default_data_types(self):
        table = TableSpec('test', ['col1'], iter([['value']]))

        assert table.data_types == []
        assert isinstance(table.data_types, list)

    def test_data_types_independent_instances(self):
        table1 = TableSpec('test1', ['col1'], iter([['value1']]))
        table2 = TableSpec('test2', ['col2'], iter([['value2']]))

        table1.data_types.append('text')

        assert table1.data_types == ['text']
        assert table2.data_types == []

    def test_equality_same_instances(self):
        table1 = TableSpec('test', ['col1', 'col2'], iter([['a', 'b']]), ['text', 'text'])
        table2 = TableSpec('test', ['col1', 'col2'], iter([['a', 'b']]), ['text', 'text'])

        assert table1 == table2

    def test_equality_different_names(self):
        table1 = TableSpec('test1', ['col1'], iter([['a']]))
        table2 = TableSpec('test2', ['col1'], iter([['a']]))

        assert table1 != table2

    def test_equality_different_headings(self):
        table1 = TableSpec('test', ['col1'], iter([['a']]))
        table2 = TableSpec('test', ['col2'], iter([['a']]))

        assert table1 != table2

    def test_equality_different_data_types(self):
        table1 = TableSpec('test', ['col1'], iter([['a']]), ['text'])
        table2 = TableSpec('test', ['col1'], iter([['a']]), ['integer'])

        assert table1 != table2

    def test_equality_ignores_rows(self):
        table1 = TableSpec('test', ['col1'], iter([['a']]), ['text'])
        table2 = TableSpec('test', ['col1'], iter([['b']]), ['text'])

        assert table1 == table2

    def test_equality_different_types(self):
        table = TableSpec('test', ['col1'], iter([['a']]))

        assert table != 'not_a_table'
        assert table != {'name': 'test', 'headings': ['col1']}
        assert table != None

    def test_to_json_basic(self):
        table = TableSpec('test_table', ['col1', 'col2'], iter([['a', 'b']]))

        expected = {
            'name': 'test_table',
            'headings': ['col1', 'col2'],
            'data_types': []
        }

        assert table.toJSON() == expected

    def test_to_json_with_data_types(self):
        table = TableSpec(
            'typed_table',
            ['id', 'name'],
            iter([[1, 'test']]),
            ['integer', 'text']
        )

        expected = {
            'name': 'typed_table',
            'headings': ['id', 'name'],
            'data_types': ['integer', 'text']
        }

        assert table.toJSON() == expected

    def test_to_json_excludes_rows(self):
        table = TableSpec('test', ['col1'], iter([['sensitive_data']]), ['text'])

        result = table.toJSON()

        assert 'rows' not in result
        assert 'sensitive_data' not in str(result)

    def test_dataclass_repr(self):
        table = TableSpec('test', ['col1'], iter([['a']]), ['text'])

        repr_str = repr(table)

        assert 'TableSpec' in repr_str
        assert 'test' in repr_str
        assert 'col1' in repr_str
        assert 'text' in repr_str

    def test_rows_iterable(self):
        rows_data = [['a'], ['b'], ['c']]
        table = TableSpec('test', ['col1'], iter(rows_data))

        consumed_rows = list(table.rows)

        assert consumed_rows == rows_data

    def test_rows_generator(self):
        def row_generator():
            yield ['row1']
            yield ['row2']
            yield ['row3']

        table = TableSpec('test', ['col1'], row_generator())

        rows_list = list(table.rows)

        assert rows_list == [['row1'], ['row2'], ['row3']]


@pytest.mark.parametrize("name,headings,rows,data_types", [
    ('simple', ['col'], [['val']], []),
    ('empty_rows', ['col1', 'col2'], [], ['text', 'text']),
    ('no_headings', [], [['val1', 'val2']], []),
    ('mixed_types', ['id', 'name', 'active'], [[1, 'test', True]], ['int', 'str', 'bool']),
    ('unicode', ['名前'], [['テスト']], ['text']),
    ('special_chars', ['col!@#'], [['val$%^']], ['text']),
])
def test_table_spec_variations(name, headings, rows, data_types):
    table = TableSpec(name, headings, iter(rows), data_types)

    assert table.name == name
    assert table.headings == headings
    assert list(table.rows) == rows
    assert table.data_types == data_types


@pytest.mark.parametrize("data_types_input,expected_data_types", [
    (None, []),
    ([], []),
    (['text'], ['text']),
    (['text', 'integer', 'boolean'], ['text', 'integer', 'boolean']),
])
def test_data_types_default_handling(data_types_input, expected_data_types):
    if data_types_input is None:
        table = TableSpec('test', ['col'], iter([['val']]))
    else:
        table = TableSpec('test', ['col'], iter([['val']]), data_types_input)

    assert table.data_types == expected_data_types


def test_table_spec_with_complex_data():
    complex_rows = [
        [{'nested': 'dict'}, ['nested', 'list'], None],
        ['string', 42, True],
        [[], {}, '']
    ]

    table = TableSpec(
        'complex_table',
        ['dict_col', 'list_col', 'mixed_col'],
        iter(complex_rows),
        ['json', 'array', 'text']
    )

    rows_list = list(table.rows)
    assert rows_list == complex_rows
    assert len(rows_list) == 3
    assert rows_list[0][0] == {'nested': 'dict'}
    assert rows_list[1][1] == 42


def test_table_spec_edge_cases():
    table1 = TableSpec('', [], iter([]))
    assert table1.name == ''

    long_name = 'x' * 1000
    table2 = TableSpec(long_name, [], iter([]))
    assert table2.name == long_name

    many_cols = [f'col_{i}' for i in range(100)]
    table3 = TableSpec('many_cols', many_cols, iter([]))
    assert len(table3.headings) == 100


@pytest.fixture
def sample_table():
    return TableSpec(
        'sample_table',
        ['id', 'name', 'value'],
        iter([[1, 'first', 10.5], [2, 'second', 20.0]]),
        ['integer', 'text', 'decimal']
    )


def test_sample_table_fixture(sample_table):
    assert sample_table.name == 'sample_table'
    assert len(sample_table.headings) == 3
    rows_list = list(sample_table.rows)
    assert len(rows_list) == 2
    assert len(sample_table.data_types) == 3


def test_table_spec_equality_with_fixture(sample_table):
    identical_table = TableSpec(
        'sample_table',
        ['id', 'name', 'value'],
        iter([[999, 'different', 'rows']]),
        ['integer', 'text', 'decimal']
    )

    assert sample_table == identical_table


def test_table_spec_json_serialization(sample_table):
    json_data = sample_table.toJSON()

    assert json_data['name'] == 'sample_table'
    assert json_data['headings'] == ['id', 'name', 'value']
    assert json_data['data_types'] == ['integer', 'text', 'decimal']
    assert 'rows' not in json_data
