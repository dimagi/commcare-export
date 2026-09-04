import datetime

import pytest

import commcare_export.writers as writers
from commcare_export.data_types import DATA_TYPES_TO_SQLALCHEMY_TYPES
from commcare_export.exceptions import (
    DeltaWriteException,
    UnwritableValueException,
)
from commcare_export.specs import TableSpec
from commcare_export.writers import DeltaTableWriter

deltalake = pytest.importorskip('deltalake')

UTC = datetime.timezone.utc


def write_table(base_uri, headings, rows, data_types=None, name='forms'):
    with DeltaTableWriter(str(base_uri)) as writer:
        writer.write_table(
            TableSpec(
                name=name,
                headings=headings,
                rows=rows,
                data_types=data_types or [],
            )
        )


def read_table(base_uri, name='forms'):
    table = deltalake.DeltaTable(f'{base_uri}/{name}')
    rows = table.to_pyarrow_table().to_pylist()
    return sorted(rows, key=lambda row: row['id'])


def test_declared_data_types_become_typed_columns(tmp_path):
    write_table(
        tmp_path,
        ['id', 'count', 'active', 'seen', 'born', 'extras'],
        [['a', '3', 'true', '2026-01-05T09:30:00', '1990-06-01', {'x': 1}]],
        data_types=[None, 'integer', 'boolean', 'datetime', 'date', 'json'],
    )
    assert read_table(tmp_path) == [{
        'id': 'a',
        'count': 3,
        'active': True,
        'seen': datetime.datetime(2026, 1, 5, 9, 30, tzinfo=UTC),
        'born': datetime.date(1990, 6, 1),
        'extras': '{"x": 1}',
    }]


def test_undeclared_columns_are_stored_as_text(tmp_path):
    write_table(
        tmp_path,
        ['id', 'count', 'when'],
        [['a', 3, datetime.datetime(2026, 1, 5, 9, 30)]],
    )
    assert read_table(tmp_path) == [{
        'id': 'a',
        'count': '3',
        'when': '2026-01-05 09:30:00',
    }]


def test_datetimes_are_stored_as_utc(tmp_path):
    write_table(
        tmp_path,
        ['id', 'seen'],
        [['a', '2026-01-05T09:30:00+02:00']],
        data_types=[None, 'datetime'],
    )
    assert read_table(tmp_path)[0]['seen'] == datetime.datetime(
        2026, 1, 5, 7, 30, tzinfo=UTC
    )


def test_second_write_updates_rows_with_matching_ids(tmp_path):
    write_table(tmp_path, ['id', 'name'], [['a', 'Ada'], ['b', 'Bo']])
    write_table(tmp_path, ['id', 'name'], [['b', 'Bob'], ['c', 'Cy']])
    assert read_table(tmp_path) == [
        {'id': 'a', 'name': 'Ada'},
        {'id': 'b', 'name': 'Bob'},
        {'id': 'c', 'name': 'Cy'},
    ]


def test_null_values_preserve_existing_values(tmp_path):
    write_table(tmp_path, ['id', 'name', 'age'], [['a', 'Ada', '30']])
    write_table(tmp_path, ['id', 'name', 'age'], [['a', None, '31']])
    assert read_table(tmp_path) == [{'id': 'a', 'name': 'Ada', 'age': '31'}]


def test_later_writes_can_add_columns(tmp_path):
    write_table(tmp_path, ['id', 'name'], [['a', 'Ada']])
    write_table(
        tmp_path,
        ['id', 'name', 'city'],
        [['a', None, 'Oslo'], ['b', 'Bo', None]],
    )
    assert read_table(tmp_path) == [
        {'id': 'a', 'name': 'Ada', 'city': 'Oslo'},
        {'id': 'b', 'name': 'Bo', 'city': None},
    ]


def test_last_row_wins_when_a_write_repeats_an_id(tmp_path):
    write_table(tmp_path, ['id', 'name'], [['a', 'Ada'], ['a', 'Adele']])
    assert read_table(tmp_path) == [{'id': 'a', 'name': 'Adele'}]


def test_null_in_a_repeated_id_does_not_erase_the_earlier_value(tmp_path):
    write_table(
        tmp_path,
        ['id', 'name', 'age'],
        [['a', 'Ada', '30'], ['a', None, '31']],
    )
    assert read_table(tmp_path) == [{'id': 'a', 'name': 'Ada', 'age': '31'}]


def test_rows_without_an_id_are_skipped(tmp_path, caplog):
    write_table(
        tmp_path,
        ['id', 'name'],
        [['a', 'Ada'], [None, 'no id'], ['short-row-cut-before-name']],
    )
    assert read_table(tmp_path) == [
        {'id': 'a', 'name': 'Ada'},
        {'id': 'short-row-cut-before-name', 'name': None},
    ]
    assert any(
        "Rows skipped for having no id in table 'forms': 1" in message
        for message in caplog.messages
    )


def test_ids_are_stored_as_strings_even_when_a_type_is_declared(tmp_path):
    write_table(
        tmp_path,
        ['id', 'count'],
        [[123, '4']],
        data_types=['integer', 'integer'],
    )
    assert read_table(tmp_path) == [{'id': '123', 'count': 4}]


def test_duplicate_headings_collapse_to_the_last_value(tmp_path):
    write_table(tmp_path, ['id', 'a', 'a'], [['x', '1', '2']])
    assert read_table(tmp_path) == [{'id': 'x', 'a': '2'}]


def test_unconvertible_values_report_their_table_and_column(tmp_path):
    with pytest.raises(UnwritableValueException) as excinfo:
        write_table(
            tmp_path,
            ['id', 'count'],
            [['a', '']],
            data_types=[None, 'integer'],
        )
    assert 'column "count" of table "forms"' in excinfo.value.message
    assert "for row id 'a'" in excinfo.value.message


def test_error_messages_truncate_long_values(tmp_path):
    with pytest.raises(UnwritableValueException) as excinfo:
        write_table(
            tmp_path,
            ['id', 'count'],
            [['a', 'x' * 500]],
            data_types=[None, 'integer'],
        )
    assert len(excinfo.value.message) < 300
    assert '...' in excinfo.value.message
    # tracebacks render str(exception), which must not carry the full
    # value either
    assert len(str(excinfo.value)) < 300


@pytest.mark.parametrize(
    'value,data_type,expected',
    [
        ('false', 'boolean', False),
        ('F', 'boolean', False),
        (0, 'boolean', False),
        (datetime.date(2026, 1, 5), 'datetime',
         datetime.datetime(2026, 1, 5, tzinfo=UTC)),
        (datetime.datetime(2026, 1, 5, 9, 30), 'datetime',
         datetime.datetime(2026, 1, 5, 9, 30, tzinfo=UTC)),
        (datetime.datetime(2026, 1, 5, 9, 30), 'date',
         datetime.date(2026, 1, 5)),
        (datetime.date(2026, 1, 5), 'date', datetime.date(2026, 1, 5)),
    ],
)
def test_value_conversions(tmp_path, value, data_type, expected):
    write_table(
        tmp_path, ['id', 'val'], [['a', value]], data_types=[None, data_type]
    )
    assert read_table(tmp_path)[0]['val'] == expected


def test_values_that_are_not_booleans_are_rejected(tmp_path):
    with pytest.raises(UnwritableValueException):
        write_table(
            tmp_path,
            ['id', 'val'],
            [['a', 'yes']],
            data_types=[None, 'boolean'],
        )


def test_id_only_tables_can_be_written_twice(tmp_path):
    write_table(tmp_path, ['id'], [['a']])
    write_table(tmp_path, ['id'], [['a'], ['b']])
    assert read_table(tmp_path) == [{'id': 'a'}, {'id': 'b'}]


def test_first_exports_append_in_chunks_and_compact(tmp_path, monkeypatch):
    monkeypatch.setattr(writers, 'DELTA_BATCH_SIZE', 3)
    write_table(
        tmp_path,
        ['id', 'name'],
        [[f'r{i}', f'n{i}'] for i in range(8)],
    )
    table = deltalake.DeltaTable(f'{tmp_path}/forms')
    assert table.to_pyarrow_table().num_rows == 8
    assert len(table.file_uris()) == 1
    operations = [entry['operation'] for entry in table.history()]
    assert operations == ['OPTIMIZE', 'WRITE', 'WRITE', 'WRITE']


def test_single_chunk_exports_make_one_commit(tmp_path):
    write_table(tmp_path, ['id', 'name'], [['a', 'Ada'], ['b', 'Bo']])
    assert deltalake.DeltaTable(f'{tmp_path}/forms').version() == 0


def test_compaction_failures_only_warn(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(writers, 'DELTA_BATCH_SIZE', 3)
    monkeypatch.setattr(
        deltalake.table.TableOptimizer,
        'compact',
        lambda self, *args, **kwargs: (_ for _ in ()).throw(
            Exception('compaction exploded')
        ),
    )
    write_table(
        tmp_path,
        ['id', 'name'],
        [[f'r{i}', f'n{i}'] for i in range(8)],
    )
    assert read_table(tmp_path) == [
        {'id': f'r{i}', 'name': f'n{i}'} for i in range(8)
    ]
    assert any(
        'Failed to compact' in message for message in caplog.messages
    )


def test_duplicate_ids_across_chunks_keep_upsert_semantics(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(writers, 'DELTA_BATCH_SIZE', 2)
    write_table(
        tmp_path,
        ['id', 'name', 'age'],
        [
            ['a', 'Ada', '30'],
            ['b', 'Bo', '9'],
            ['a', None, '31'],
            ['c', 'Cy', '1'],
            ['a', 'Adele', None],
        ],
    )
    assert read_table(tmp_path) == [
        {'id': 'a', 'name': 'Adele', 'age': '31'},
        {'id': 'b', 'name': 'Bo', 'age': '9'},
        {'id': 'c', 'name': 'Cy', 'age': '1'},
    ]


def test_existing_tables_merge_in_chunks(tmp_path, monkeypatch):
    write_table(tmp_path, ['id', 'name'], [['a', 'Ada'], ['b', 'Bo']])
    monkeypatch.setattr(writers, 'DELTA_BATCH_SIZE', 2)
    write_table(
        tmp_path,
        ['id', 'name'],
        [['a', None], ['c', 'Cy'], ['d', 'Dee']],
    )
    assert read_table(tmp_path) == [
        {'id': 'a', 'name': 'Ada'},
        {'id': 'b', 'name': 'Bo'},
        {'id': 'c', 'name': 'Cy'},
        {'id': 'd', 'name': 'Dee'},
    ]


def test_error_messages_neutralize_control_characters(tmp_path):
    with pytest.raises(UnwritableValueException) as excinfo:
        write_table(
            tmp_path,
            ['id', 'count'],
            [['a', 'line1\nFORGED LOG LINE\x1b[31m']],
            data_types=[None, 'integer'],
        )
    assert '\n' not in str(excinfo.value)
    assert '\x1b' not in str(excinfo.value)


def test_every_declared_data_type_has_an_arrow_mapping(tmp_path):
    writer = DeltaTableWriter(str(tmp_path))
    assert set(DATA_TYPES_TO_SQLALCHEMY_TYPES) <= set(writer.arrow_types)


@pytest.mark.parametrize('data_type', sorted(DATA_TYPES_TO_SQLALCHEMY_TYPES))
def test_every_declared_data_type_converts_a_value(tmp_path, data_type):
    values = {
        'boolean': True,
        'date': '2026-01-05',
        'datetime': '2026-01-05T09:30:00',
        'integer': 3,
        'json': {'x': 1},
        'text': 'x',
    }
    write_table(
        tmp_path,
        ['id', 'val'],
        [['a', values[data_type]]],
        data_types=[None, data_type],
    )
    assert read_table(tmp_path)[0]['val'] is not None


def test_unknown_declared_types_warn_and_fall_back_to_text(tmp_path, caplog):
    write_table(
        tmp_path, ['id', 'val'], [['a', 3]], data_types=[None, 'bogus']
    )
    assert read_table(tmp_path) == [{'id': 'a', 'val': '3'}]
    assert any(
        "Found unknown data type 'bogus'" in message
        for message in caplog.messages
    )


def test_partial_dates_are_rejected_rather_than_guessed(tmp_path):
    with pytest.raises(UnwritableValueException):
        write_table(
            tmp_path,
            ['id', 'seen'],
            [['a', 'Jan 2026']],
            data_types=[None, 'datetime'],
        )


def test_missing_delta_extra_reports_how_to_install_it(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_deltalake(name, *args, **kwargs):
        if name in ('deltalake', 'pyarrow'):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', no_deltalake)
    with pytest.raises(Exception, match=r'commcare-export\[delta\]'):
        DeltaTableWriter('exports')


def test_floats_in_integer_columns_are_rounded(tmp_path):
    write_table(
        tmp_path, ['id', 'count'], [['a', 3.7]], data_types=[None, 'integer']
    )
    assert read_table(tmp_path) == [{'id': 'a', 'count': 4}]


def test_bytes_are_stored_as_text(tmp_path):
    write_table(
        tmp_path, ['id', 'blob'], [['a', b'hello'], ['b', b'\xff\xfe']]
    )
    rows = read_table(tmp_path)
    assert rows[0] == {'id': 'a', 'blob': 'hello'}
    assert rows[1]['blob'] == '�' * 2


def test_column_names_with_backticks_are_rejected(tmp_path):
    with pytest.raises(DeltaWriteException) as excinfo:
        write_table(tmp_path, ['id', 'a`b'], [['x', 'y']])
    assert 'column name' in excinfo.value.message


def test_type_conflicts_across_writes_report_the_table(tmp_path):
    write_table(
        tmp_path, ['id', 'n'], [['a', '2']], data_types=[None, 'integer']
    )
    with pytest.raises(DeltaWriteException) as excinfo:
        write_table(tmp_path, ['id', 'n'], [['b', 'not-a-number']])
    assert 'forms' in excinfo.value.message


def test_column_names_that_need_quoting(tmp_path):
    headings = ['id', 'has space', 'select', 'quo"te']
    write_table(tmp_path, headings, [['a', 'x', 'y', 'z']])
    write_table(tmp_path, headings, [['a', 'x2', None, 'z2']])
    assert read_table(tmp_path) == [{
        'id': 'a',
        'has space': 'x2',
        'select': 'y',
        'quo"te': 'z2',
    }]


@pytest.mark.parametrize(
    'table_name',
    [
        'up/../and/out', '..', 'a\\b', '%2e%2e', '.', '', 'a?b', 'a#b',
        'a:b', 'a[b', 'a]b', 'a^b', 'a|b',
    ],
)
def test_table_names_cannot_escape_the_base_uri(tmp_path, table_name):
    with pytest.raises(DeltaWriteException) as excinfo:
        write_table(tmp_path, ['id'], [['a']], name=table_name)
    assert 'table name' in excinfo.value.message


def test_tables_without_an_id_column_are_rejected(tmp_path):
    with pytest.raises(DeltaWriteException) as excinfo:
        write_table(tmp_path, ['name'], [['Ada']])
    assert "'id' column" in excinfo.value.message


def test_each_table_is_written_under_the_base_uri(tmp_path):
    write_table(tmp_path, ['id'], [['a']], name='forms')
    write_table(tmp_path, ['id'], [['b']], name='cases')
    assert read_table(tmp_path, 'forms') == [{'id': 'a'}]
    assert read_table(tmp_path, 'cases') == [{'id': 'b'}]
