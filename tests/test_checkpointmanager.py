# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import datetime

import pytest
import sqlalchemy

from commcare_export.checkpoint import CheckpointManager


@pytest.fixture()
def manager(db_params):
    manager = CheckpointManager(db_params['url'], poolclass=sqlalchemy.pool.NullPool)
    try:
        yield manager
    finally:
        with manager:
            manager.connection.execute(manager.sqlalchemy.sql.text('DROP TABLE IF EXISTS commcare_export_runs'))
            manager.connection.execute(manager.sqlalchemy.sql.text('DROP TABLE IF EXISTS alembic_version'))


class TestCheckpointManager(object):
    def test_create_checkpoint_table(self, manager):
        manager.create_checkpoint_table()
        with manager:
            assert 'commcare_export_runs' in manager.metadata.tables

    def test_checkpoint_table_exists(self, manager):
        self.test_create_checkpoint_table(manager)
        with manager:
            manager.connection.execute(manager.sqlalchemy.sql.text('DROP TABLE alembic_version'))
        manager.create_checkpoint_table()

    def test_get_time_of_last_run(self, manager):
        manager.create_checkpoint_table()
        with manager:
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=True)
            second_run = datetime.datetime.utcnow()
            manager.set_checkpoint('query', '123', second_run, run_complete=True)

            assert manager.get_time_of_last_run('123') == second_run.isoformat()

    def test_clean_on_final_run(self, manager):
        manager.create_checkpoint_table()
        with manager:
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=False)
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=False)

            def _get_non_final_rows_count():
                cursor = manager.connection.execute(
                    manager.sqlalchemy.sql.text('select count(*) from {} where final = :final'.format(manager.table_name)),
                    final=False
                )
                for row in cursor:
                    return row[0]

            assert _get_non_final_rows_count() == 2
            manager.set_checkpoint('query', '123', datetime.datetime.utcnow(), run_complete=True)
            assert _get_non_final_rows_count() == 0
