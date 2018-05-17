import datetime
import logging
import uuid

import os

from commcare_export.writers import SqlMixin

logger = logging.getLogger(__name__)
repo_root = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))


class CheckpointManager(SqlMixin):
    table_name = 'commcare_export_runs'
    migrations_repository = os.path.join(repo_root, 'migrations')

    def set_checkpoint(self, query, query_md5, checkpoint_time=None, run_complete=False):
        logger.info('Setting checkpoint')
        checkpoint_time = checkpoint_time or datetime.datetime.utcnow()
        self._insert_checkpoint(
            id=uuid.uuid4().hex,
            query_file_name=query,
            query_file_md5=query_md5,
            since_param=checkpoint_time.isoformat(),
            time_of_run=datetime.datetime.utcnow().isoformat(),
            final=run_complete
        )
        if run_complete:
            self._cleanup(query_md5)

    def create_checkpoint_table(self):
        from alembic import command, config
        cfg = config.Config(os.path.join(self.migrations_repository, 'alembic.ini'))
        cfg.set_main_option('script_location', self.migrations_repository)
        with self.engine.begin() as connection:
            cfg.attributes['connection'] = connection
            command.upgrade(cfg, "head")

    def _insert_checkpoint(self, **row):
        table = self.table(self.table_name)
        insert = table.insert().values(**row)
        self.connection.execute(insert)

    def _cleanup(self, query_md5):
        sql = """
           DELETE FROM {}
           WHERE final = :final
           AND query_file_md5 = :md5
       """.format(self.table_name)
        self.connection.execute(
            self.sqlalchemy.sql.text(sql),
            final=False,
            md5=query_md5,
        )

    def get_time_of_last_run(self, query_file_md5):
        if 'commcare_export_runs' in self.metadata.tables:
            sql = """
                SELECT since_param FROM commcare_export_runs
                WHERE query_file_md5 = :query_file_md5 ORDER BY since_param DESC
            """
            cursor = self.connection.execute(
                self.sqlalchemy.sql.text(sql),
                query_file_md5=query_file_md5
            )
            for row in cursor:
                return row[0]
