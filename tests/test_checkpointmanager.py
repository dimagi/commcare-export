# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import datetime
import uuid

import pytest
import sqlalchemy

from commcare_export.checkpoint import CheckpointManager, Checkpoint, session_scope


@pytest.fixture()
def manager(db_params):
    manager = CheckpointManager(db_params['url'], 'query', '123', 'test', 'hq', poolclass=sqlalchemy.pool.NullPool)
    try:
        yield manager
    finally:
        with manager:
            manager.connection.execute(sqlalchemy.sql.text('DROP TABLE IF EXISTS commcare_export_runs'))
            manager.connection.execute(sqlalchemy.sql.text('DROP TABLE IF EXISTS alembic_version'))


@pytest.mark.dbtest
class TestCheckpointManager(object):
    def test_create_checkpoint_table(self, manager, revision='head'):
        manager.create_checkpoint_table(revision)
        with manager:
            assert 'commcare_export_runs' in manager.metadata.tables

    def test_checkpoint_table_exists(self, manager):
        # Test that the migrations don't fail for tables that existed before
        # migrations were used.
        # This test can be removed at some point in the future.
        self.test_create_checkpoint_table(manager, '9945abb4ec70')
        with manager:
            manager.connection.execute(sqlalchemy.sql.text('DROP TABLE alembic_version'))
        manager.create_checkpoint_table()

    def test_get_time_of_last_checkpoint(self, manager):
        manager.create_checkpoint_table()
        manager = manager.for_dataset('form', ['t1'])
        manager.set_checkpoint(datetime.datetime.utcnow())
        second_run = datetime.datetime.utcnow()
        manager.set_checkpoint(second_run)

        assert manager.get_time_of_last_checkpoint() == second_run.isoformat()

    def test_get_last_checkpoint_no_args(self, manager):
        # test that we can still get the time of last run no project and commcare args
        manager.create_checkpoint_table()
        with session_scope(manager.Session) as session:
            since_param = datetime.datetime.utcnow().isoformat()
            session.add(Checkpoint(
                id=uuid.uuid4().hex,
                query_file_name=manager.query,
                query_file_md5=manager.query_md5,
                project=None,
                commcare=None,
                since_param=since_param,
                time_of_run=datetime.datetime.utcnow().isoformat(),
                final=True
            ))
        manager = manager.for_dataset('form', ['t1', 't2'])
        checkpoint = manager.get_last_checkpoint()
        assert checkpoint.since_param == since_param
        assert checkpoint.project == manager.project
        assert checkpoint.commcare == manager.commcare
        assert len(manager.get_latest_checkpoints()) == 2

    def test_get_last_checkpoint_no_table(self, manager):
        # test that we can still get the time of last run no table
        # also tests that new checkoints are created with the tables
        manager.create_checkpoint_table()
        with session_scope(manager.Session) as session:
            since_param = datetime.datetime.utcnow().isoformat()
            session.add(Checkpoint(
                id=uuid.uuid4().hex,
                query_file_name=manager.query,
                query_file_md5=manager.query_md5,
                project=None,
                commcare=None,
                since_param=since_param,
                time_of_run=datetime.datetime.utcnow().isoformat(),
                final=True
            ))

            session.add(Checkpoint(
                id=uuid.uuid4().hex,
                query_file_name=manager.query,
                query_file_md5=manager.query_md5,
                project=manager.project,
                commcare=manager.commcare,
                since_param=since_param,
                time_of_run=datetime.datetime.utcnow().isoformat(),
                final=True
            ))
        manager = manager.for_dataset('form', ['t1', 't2'])
        checkpoint = manager.get_last_checkpoint()
        assert checkpoint.since_param == since_param
        assert checkpoint.table_name in manager.table_names
        checkpoints = manager.get_latest_checkpoints()
        assert len(checkpoints) == 2
        assert {c.table_name for c in checkpoints} == set(manager.table_names)

    def test_clean_on_final_run(self, manager):
        manager.create_checkpoint_table()
        manager = manager.for_dataset('form', ['t1'])
        manager.set_checkpoint(datetime.datetime.utcnow(), doc_id="1")
        manager.set_checkpoint(datetime.datetime.utcnow(), doc_id="2")

        def _get_non_final_rows_count():
            with session_scope(manager.Session) as session:
                return session.query(Checkpoint).filter_by(final=False).count()

        assert _get_non_final_rows_count() == 2
        manager.set_checkpoint(datetime.datetime.utcnow(), True, doc_id="3")
        assert _get_non_final_rows_count() == 0

    def test_get_time_of_last_checkpoint_with_key(self, manager):
        manager.create_checkpoint_table()
        manager = manager.for_dataset('form', ['t1'])
        manager.key = 'my key'
        last_run_time = datetime.datetime.utcnow()
        manager.set_checkpoint(last_run_time)

        assert manager.get_time_of_last_checkpoint() == last_run_time.isoformat()
        manager.key = None
        assert manager.get_time_of_last_checkpoint() is None

    def test_multiple_tables(self, manager):
        manager.create_checkpoint_table()
        t1 = uuid.uuid4().hex
        t2 = uuid.uuid4().hex
        manager = manager.for_dataset('form', [t1, t2])
        last_run_time = datetime.datetime.utcnow()
        doc_id = uuid.uuid4().hex
        manager.set_checkpoint(last_run_time, doc_id=doc_id)

        assert manager.for_dataset('form', [t1]).get_time_of_last_checkpoint() == last_run_time.isoformat()
        assert manager.for_dataset('form', [t2]).get_time_of_last_checkpoint() == last_run_time.isoformat()
        assert manager.for_dataset('form', ['t3']).get_last_checkpoint() is None

        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) == 2
        assert {checkpoints[0].table_name, checkpoints[1].table_name} == {t1, t2}
        assert {checkpoints[0].last_doc_id, checkpoints[1].last_doc_id} == {doc_id}

    def test_get_latest_checkpoints(self, manager):
        manager.create_checkpoint_table()
        manager = manager.for_dataset('form', ['t1', 't2'])
        manager.set_checkpoint(datetime.datetime.utcnow())

        manager.query_md5 = '456'
        manager.set_checkpoint(datetime.datetime.utcnow())
        latest_time = datetime.datetime.utcnow()
        manager.set_checkpoint(latest_time)

        checkpoints = manager.get_latest_checkpoints()
        assert len(checkpoints) == 2
        assert [c.table_name for c in checkpoints] == ['t1', 't2']
        assert {c.query_file_md5 for c in checkpoints} == {'456'}
        assert {c.since_param for c in checkpoints} == {latest_time.isoformat()}
