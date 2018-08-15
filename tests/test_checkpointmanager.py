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

    def test_get_time_of_last_run(self, manager):
        manager.create_checkpoint_table()
        manager.set_batch_checkpoint(datetime.datetime.utcnow())
        second_run = datetime.datetime.utcnow()
        manager.set_batch_checkpoint(second_run)

        assert manager.get_time_of_last_run() == second_run.isoformat()

    def test_get_time_of_last_run_no_args(self, manager):
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
        assert manager.get_time_of_last_run() == since_param

    def test_clean_on_final_run(self, manager):
        manager.create_checkpoint_table()
        manager.set_batch_checkpoint(datetime.datetime.utcnow())
        manager.set_batch_checkpoint(datetime.datetime.utcnow())

        def _get_non_final_rows_count():
            with session_scope(manager.Session) as session:
                return session.query(Checkpoint).filter_by(final=False).count()

        assert _get_non_final_rows_count() == 2
        manager.set_final_checkpoint()
        assert _get_non_final_rows_count() == 0

    def test_get_time_of_last_run__with_key(self, manager):
        manager.create_checkpoint_table()
        manager.key = 'my key'
        last_run_time = datetime.datetime.utcnow()
        manager.set_batch_checkpoint(last_run_time)

        assert manager.get_time_of_last_run() == last_run_time.isoformat()
        manager.key = None
        assert manager.get_time_of_last_run() is None

