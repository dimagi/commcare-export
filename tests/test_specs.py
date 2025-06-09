import pytest
from commcare_export.specs import TableSpec


class TestTableSpec:
    """Test suite for TableSpec dataclass."""

    def test_basic_instantiation(self):
        """Test basic instantiation with positional arguments."""
        table = TableSpec('test', ['col1', 'col2'], [['a', 'b'], ['c', 'd']])
        
        assert table.name == 'test'
        assert table.headings == ['col1', 'col2']
        assert table.rows == [['a', 'b'], ['c', 'd']]
        assert table.data_types == []

    def test_keyword_instantiation(self):
        """Test instantiation with keyword arguments."""
        table = TableSpec(
            name='test_table',
            headings=['col1', 'col2'],
            rows=[['x', 'y']],
            data_types=['text', 'integer']
        )
        
        assert table.name == 'test_table'
        assert table.headings == ['col1', 'col2']
        assert table.rows == [['x', 'y']]
        assert table.data_types == ['text', 'integer']

    def test_unpacking_instantiation(self):
        """Test instantiation with dictionary unpacking."""
        table_data = {
            'name': 'unpacked_table',
            'headings': ['id', 'value'],
            'rows': [[1, 'test'], [2, 'data']],
            'data_types': ['integer', 'text']
        }
        
        table = TableSpec(**table_data)
        
        assert table.name == 'unpacked_table'
        assert table.headings == ['id', 'value']
        assert table.rows == [[1, 'test'], [2, 'data']]
        assert table.data_types == ['integer', 'text']

    def test_default_data_types(self):
        """Test that data_types defaults to empty list."""
        table = TableSpec('test', ['col1'], [['value']])
        
        assert table.data_types == []
        assert isinstance(table.data_types, list)

    def test_data_types_independent_instances(self):
        """Test that default data_types are independent between instances."""
        table1 = TableSpec('test1', ['col1'], [['value1']])
        table2 = TableSpec('test2', ['col2'], [['value2']])
        
        table1.data_types.append('text')
        
        assert table1.data_types == ['text']
        assert table2.data_types == []

    def test_equality_same_instances(self):
        """Test equality between identical instances."""
        table1 = TableSpec('test', ['col1', 'col2'], [['a', 'b']], ['text', 'text'])
        table2 = TableSpec('test', ['col1', 'col2'], [['a', 'b']], ['text', 'text'])
        
        assert table1 == table2

    def test_equality_different_names(self):
        """Test inequality when names differ."""
        table1 = TableSpec('test1', ['col1'], [['a']])
        table2 = TableSpec('test2', ['col1'], [['a']])
        
        assert table1 != table2

    def test_equality_different_headings(self):
        """Test inequality when headings differ."""
        table1 = TableSpec('test', ['col1'], [['a']])
        table2 = TableSpec('test', ['col2'], [['a']])
        
        assert table1 != table2

    def test_equality_different_data_types(self):
        """Test inequality when data_types differ."""
        table1 = TableSpec('test', ['col1'], [['a']], ['text'])
        table2 = TableSpec('test', ['col1'], [['a']], ['integer'])
        
        assert table1 != table2

    def test_equality_ignores_rows(self):
        """Test that equality comparison ignores rows (as in original implementation)."""
        table1 = TableSpec('test', ['col1'], [['a']], ['text'])
        table2 = TableSpec('test', ['col1'], [['b']], ['text'])
        
        assert table1 == table2

    def test_equality_different_types(self):
        """Test inequality with different object types."""
        table = TableSpec('test', ['col1'], [['a']])
        
        assert table != 'not_a_table'
        assert table != {'name': 'test', 'headings': ['col1']}
        assert table != None

    def test_to_json_basic(self):
        """Test toJSON method with basic data."""
        table = TableSpec('test_table', ['col1', 'col2'], [['a', 'b']])
        
        expected = {
            'name': 'test_table',
            'headings': ['col1', 'col2'],
            'data_types': []
        }
        
        assert table.toJSON() == expected

    def test_to_json_with_data_types(self):
        """Test toJSON method with data types."""
        table = TableSpec(
            'typed_table',
            ['id', 'name'],
            [[1, 'test']],
            ['integer', 'text']
        )
        
        expected = {
            'name': 'typed_table',
            'headings': ['id', 'name'],
            'data_types': ['integer', 'text']
        }
        
        assert table.toJSON() == expected

    def test_to_json_excludes_rows(self):
        """Test that toJSON does not include rows."""
        table = TableSpec('test', ['col1'], [['sensitive_data']], ['text'])
        
        result = table.toJSON()
        
        assert 'rows' not in result
        assert 'sensitive_data' not in str(result)

    def test_dataclass_repr(self):
        """Test that dataclass provides automatic repr."""
        table = TableSpec('test', ['col1'], [['a']], ['text'])
        
        repr_str = repr(table)
        
        assert 'TableSpec' in repr_str
        assert 'test' in repr_str
        assert 'col1' in repr_str
        assert 'text' in repr_str

    def test_mutable_fields(self):
        """Test that fields are mutable after instantiation."""
        table = TableSpec('test', ['col1'], [['a']])
        
        # Test mutating fields
        table.name = 'modified'
        table.headings.append('col2')
        table.rows.append(['b'])
        table.data_types.append('text')
        
        assert table.name == 'modified'
        assert table.headings == ['col1', 'col2']
        assert table.rows == [['a'], ['b']]
        assert table.data_types == ['text']


# Parametrized tests for different data combinations
@pytest.mark.parametrize("name,headings,rows,data_types", [
    ('simple', ['col'], [['val']], []),
    ('empty_rows', ['col1', 'col2'], [], ['text', 'text']),
    ('no_headings', [], [['val1', 'val2']], []),
    ('mixed_types', ['id', 'name', 'active'], [[1, 'test', True]], ['int', 'str', 'bool']),
    ('unicode', ['名前'], [['テスト']], ['text']),
    ('special_chars', ['col!@#'], [['val$%^']], ['text']),
])
def test_table_spec_variations(name, headings, rows, data_types):
    """Test TableSpec with various data combinations."""
    table = TableSpec(name, headings, rows, data_types)
    
    assert table.name == name
    assert table.headings == headings
    assert table.rows == rows
    assert table.data_types == data_types


@pytest.mark.parametrize("data_types_input,expected_data_types", [
    (None, []),
    ([], []),
    (['text'], ['text']),
    (['text', 'integer', 'boolean'], ['text', 'integer', 'boolean']),
])
def test_data_types_default_handling(data_types_input, expected_data_types):
    """Test various data_types input scenarios."""
    if data_types_input is None:
        table = TableSpec('test', ['col'], [['val']])
    else:
        table = TableSpec('test', ['col'], [['val']], data_types_input)
    
    assert table.data_types == expected_data_types


def test_table_spec_with_complex_data():
    """Test TableSpec with complex nested data structures."""
    complex_rows = [
        [{'nested': 'dict'}, ['nested', 'list'], None],
        ['string', 42, True],
        [[], {}, '']
    ]
    
    table = TableSpec(
        'complex_table',
        ['dict_col', 'list_col', 'mixed_col'],
        complex_rows,
        ['json', 'array', 'text']
    )
    
    assert table.rows == complex_rows
    assert len(table.rows) == 3
    assert table.rows[0][0] == {'nested': 'dict'}
    assert table.rows[1][1] == 42


def test_table_spec_edge_cases():
    """Test TableSpec with edge case inputs."""
    # Empty string name
    table1 = TableSpec('', [], [])
    assert table1.name == ''
    
    # Very long name
    long_name = 'x' * 1000
    table2 = TableSpec(long_name, [], [])
    assert table2.name == long_name
    
    # Large number of columns
    many_cols = [f'col_{i}' for i in range(100)]
    table3 = TableSpec('many_cols', many_cols, [])
    assert len(table3.headings) == 100


@pytest.fixture
def sample_table():
    """Fixture providing a sample TableSpec for testing."""
    return TableSpec(
        'sample_table',
        ['id', 'name', 'value'],
        [[1, 'first', 10.5], [2, 'second', 20.0]],
        ['integer', 'text', 'decimal']
    )


def test_sample_table_fixture(sample_table):
    """Test using the sample_table fixture."""
    assert sample_table.name == 'sample_table'
    assert len(sample_table.headings) == 3
    assert len(sample_table.rows) == 2
    assert len(sample_table.data_types) == 3


def test_table_spec_equality_with_fixture(sample_table):
    """Test equality using fixture."""
    identical_table = TableSpec(
        'sample_table',
        ['id', 'name', 'value'],
        [[999, 'different', 'rows']],  # Different rows should not affect equality
        ['integer', 'text', 'decimal']
    )
    
    assert sample_table == identical_table


def test_table_spec_json_serialization(sample_table):
    """Test JSON serialization with fixture."""
    json_data = sample_table.toJSON()
    
    assert json_data['name'] == 'sample_table'
    assert json_data['headings'] == ['id', 'name', 'value']
    assert json_data['data_types'] == ['integer', 'text', 'decimal']
    assert 'rows' not in json_data