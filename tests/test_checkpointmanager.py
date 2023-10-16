import datetime
import uuid

import sqlalchemy

import pytest
from commcare_export.checkpoint import (
    Checkpoint,
    CheckpointManager,
    CheckpointManagerProvider,
    session_scope,
)
from commcare_export.commcare_minilinq import PaginationMode


@pytest.fixture()
def manager(db_params):
    manager = CheckpointManager(
        db_params['url'],
        'query',
        '123',
        'test',
        'hq',
        poolclass=sqlalchemy.pool.NullPool
    )
    try:
        yield manager
    finally:
        with manager:
            manager.connection.execute(
                sqlalchemy.sql
                .text('DROP TABLE IF EXISTS commcare_export_runs')
            )
            manager.connection.execute(
                sqlalchemy.sql.text('DROP TABLE IF EXISTS alembic_version')
            )


@pytest.fixture()
def configured_manager(manager):
    manager.create_checkpoint_table()
    return manager


@pytest.mark.dbtest
class TestCheckpointManager(object):

    def test_create_checkpoint_table(self, manager, revision='head'):
        manager.create_checkpoint_table(revision)
        with manager:
            table = manager.get_table('commcare_export_runs')
            assert table is not None

    def test_checkpoint_table_exists(self, manager):
        # Test that the migrations don't fail for tables that existed before
        # migrations were used.
        # This test can be removed at some point in the future.
        self.test_create_checkpoint_table(manager, '9945abb4ec70')
        with manager:
            manager.connection.execute(
                sqlalchemy.sql.text('DROP TABLE alembic_version')
            )
        manager.create_checkpoint_table()

    def test_get_time_of_last_checkpoint(self, configured_manager):
        manager = configured_manager.for_dataset('form', ['t1'])
        manager.set_checkpoint(
            datetime.datetime.utcnow(), PaginationMode.date_indexed
        )
        second_run = datetime.datetime.utcnow()
        manager.set_checkpoint(second_run, PaginationMode.date_indexed)

        assert manager.get_time_of_last_checkpoint() == second_run.isoformat()

    def test_get_last_checkpoint_no_args(self, configured_manager):
        # test that we can still get the time of last run no project and commcare args
        with session_scope(configured_manager.Session) as session:
            since_param = datetime.datetime.utcnow().isoformat()
            session.add(
                Checkpoint(
                    id=uuid.uuid4().hex,
                    query_file_name=configured_manager.query,
                    query_file_md5=configured_manager.query_md5,
                    project=None,
                    commcare=None,
                    since_param=since_param,
                    time_of_run=datetime.datetime.utcnow().isoformat(),
                    final=True
                )
            )
        manager = configured_manager.for_dataset('form', ['t1', 't2'])
        checkpoint = manager.get_last_checkpoint()
        assert checkpoint.since_param == since_param
        assert checkpoint.project == manager.project
        assert checkpoint.commcare == manager.commcare
        assert len(manager.get_latest_checkpoints()) == 2

    def test_get_last_checkpoint_no_table(self, configured_manager):
        # test that we can still get the time of last run no table
        # also tests that new checkoints are created with the tables
        with session_scope(configured_manager.Session) as session:
            since_param = datetime.datetime.utcnow().isoformat()
            session.add(
                Checkpoint(
                    id=uuid.uuid4().hex,
                    query_file_name=configured_manager.query,
                    query_file_md5=configured_manager.query_md5,
                    project=None,
                    commcare=None,
                    since_param=since_param,
                    time_of_run=datetime.datetime.utcnow().isoformat(),
                    final=True
                )
            )

            session.add(
                Checkpoint(
                    id=uuid.uuid4().hex,
                    query_file_name=configured_manager.query,
                    query_file_md5=configured_manager.query_md5,
                    project=configured_manager.project,
                    commcare=configured_manager.commcare,
                    since_param=since_param,
                    time_of_run=datetime.datetime.utcnow().isoformat(),
                    final=True
                )
            )
        manager = configured_manager.for_dataset('form', ['t1', 't2'])
        checkpoint = manager.get_last_checkpoint()
        assert checkpoint.since_param == since_param
        assert checkpoint.table_name in manager.table_names
        checkpoints = manager.get_latest_checkpoints()
        assert len(checkpoints) == 2
        assert {c.table_name for c in checkpoints} == set(manager.table_names)

    def test_clean_on_final_run(self, configured_manager):
        manager = configured_manager.for_dataset('form', ['t1'])
        manager.set_checkpoint(
            datetime.datetime.utcnow(),
            PaginationMode.date_indexed,
            doc_id="1"
        )
        manager.set_checkpoint(
            datetime.datetime.utcnow(),
            PaginationMode.date_indexed,
            doc_id="2"
        )

        def _get_non_final_rows_count():
            with session_scope(manager.Session) as session:
                return session.query(Checkpoint).filter_by(final=False).count()

        assert _get_non_final_rows_count() == 2
        manager.set_checkpoint(
            datetime.datetime.utcnow(),
            PaginationMode.date_indexed,
            True,
            doc_id="3"
        )
        assert _get_non_final_rows_count() == 0

    def test_get_time_of_last_checkpoint_with_key(self, configured_manager):
        manager = configured_manager.for_dataset('form', ['t1'])
        manager.key = 'my key'
        last_run_time = datetime.datetime.utcnow()
        manager.set_checkpoint(last_run_time, PaginationMode.date_indexed)

        assert manager.get_time_of_last_checkpoint(
        ) == last_run_time.isoformat()
        manager.key = None
        assert manager.get_time_of_last_checkpoint() is None

    def test_multiple_tables(self, configured_manager):
        t1 = uuid.uuid4().hex
        t2 = uuid.uuid4().hex
        manager = configured_manager.for_dataset('form', [t1, t2])
        last_run_time = datetime.datetime.utcnow()
        doc_id = uuid.uuid4().hex
        manager.set_checkpoint(
            last_run_time, PaginationMode.date_indexed, doc_id=doc_id
        )

        assert manager.for_dataset('form', [
            t1
        ]).get_time_of_last_checkpoint() == last_run_time.isoformat()
        assert manager.for_dataset('form', [
            t2
        ]).get_time_of_last_checkpoint() == last_run_time.isoformat()
        assert manager.for_dataset('form',
                                   ['t3']).get_last_checkpoint() is None

        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) == 2
        assert {checkpoints[0].table_name,
                checkpoints[1].table_name} == {t1, t2}
        assert {checkpoints[0].last_doc_id,
                checkpoints[1].last_doc_id} == {doc_id}

    def test_get_latest_checkpoints(self, configured_manager):
        manager = configured_manager.for_dataset('form', ['t1', 't2'])
        manager.set_checkpoint(
            datetime.datetime.utcnow(), PaginationMode.date_indexed
        )

        manager.query_md5 = '456'
        manager.set_checkpoint(
            datetime.datetime.utcnow(), PaginationMode.date_indexed
        )
        latest_time = datetime.datetime.utcnow()
        manager.set_checkpoint(latest_time, PaginationMode.date_indexed)

        checkpoints = manager.get_latest_checkpoints()
        assert len(checkpoints) == 2
        assert [c.table_name for c in checkpoints] == ['t1', 't2']
        assert {c.query_file_md5 for c in checkpoints} == {'456'}
        assert {c.since_param for c in checkpoints
               } == {latest_time.isoformat()}


@pytest.mark.parametrize(
    'since, start_over, expected_since, expected_paginator', [
        (None, True, None, PaginationMode.date_indexed),
        ('since', False, 'since', PaginationMode.date_indexed),
        (None, False, None, PaginationMode.date_indexed),
    ]
)
def test_checkpoint_details_static(
    since,
    start_over,
    expected_since,
    expected_paginator,
):
    cmp = CheckpointManagerProvider(None, since, start_over)
    assert expected_since == cmp.get_since(None)
    assert expected_paginator == cmp.get_pagination_mode('', None)


@pytest.mark.dbtest
class TestCheckpointManagerProvider(object):

    def test_checkpoint_details_no_checkpoint(self, configured_manager):
        manager = configured_manager.for_dataset('form', ['t1'])
        assert None is CheckpointManagerProvider().get_since(manager)
        assert PaginationMode.date_indexed == CheckpointManagerProvider(
        ).get_pagination_mode('form', manager)

    def test_checkpoint_details_latest_from_db(self, configured_manager):
        data_source = 'form'
        manager = configured_manager.for_dataset(data_source, ['t1'])

        self._test_checkpoint_details(
            manager, datetime.datetime.utcnow(), PaginationMode.date_modified, data_source
        )
        self._test_checkpoint_details(
            manager, datetime.datetime.utcnow(), PaginationMode.date_indexed, data_source
        )
        self._test_checkpoint_details(
            manager, datetime.datetime.utcnow(), PaginationMode.date_modified, data_source
        )

    def _test_checkpoint_details(
        self,
        manager,
        checkpoint_date,
        pagination_mode,
        data_source,
    ):
        manager.set_checkpoint(checkpoint_date, pagination_mode)

        cmp = CheckpointManagerProvider()
        assert pagination_mode == cmp.get_pagination_mode(data_source, manager)
        assert checkpoint_date == cmp.get_since(manager)
