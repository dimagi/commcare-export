import datetime
import logging
import uuid

from commcare_export.writers import SqlMixin

logger = logging.getLogger(__name__)


class CheckpointManager(SqlMixin):
    table_name = 'commcare_export_runs'

    def set_checkpoint(self, query, query_md5, checkpoint_time=None, run_complete=False):
        logger.info('Setting checkpoint')
        checkpoint_time = checkpoint_time or datetime.datetime.utcnow()
        self._insert_checkpoint(
            id=uuid.uuid4().hex,
            query_file_name=query,
            query_file_md5=query_md5,
            time_of_run=checkpoint_time.isoformat(),
            final=run_complete
        )
        if run_complete:
            self._cleanup(query_md5)

    def create_checkpoint_table(self):
        columns = self._get_checkpoint_table_columns()
        self._migrate_checkpoint_table(columns)

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

    def _migrate_checkpoint_table(self, columns):
        ctx = self.alembic.migration.MigrationContext.configure(self.connection)
        op = self.alembic.operations.Operations(ctx)
        reflect = False
        if not self.table_name in self.metadata.tables:
            op.create_table(self.table_name, *columns)
            reflect = True
        else:
            existing_columns = {c.name: c for c in self.table(self.table_name).columns}
            for column in columns:
                if column.name not in existing_columns:
                    op.add_column(self.table_name, column)
                    reflect = True
        if reflect:
            self.metadata.clear()
            self.metadata.reflect()

    def _get_checkpoint_table_columns(self):
        return [
            self.get_id_column(),
            self.sqlalchemy.Column('query_file_name',
                                   self.sqlalchemy.Unicode(self.MAX_VARCHAR_LEN, collation=self.collation)),
            self.sqlalchemy.Column('query_file_md5', self.sqlalchemy.Unicode(32, collation=self.collation)),
            self.sqlalchemy.Column('time_of_run', self.sqlalchemy.Unicode(32, collation=self.collation)),
            self.sqlalchemy.Column('final', self.sqlalchemy.Boolean()),
        ]

    def get_time_of_last_run(self, query_file_md5):
        if 'commcare_export_runs' in self.metadata.tables:
            sql = """
                SELECT time_of_run FROM commcare_export_runs
                WHERE query_file_md5 = :query_file_md5 ORDER BY time_of_run DESC
            """
            cursor = self.connection.execute(
                self.sqlalchemy.sql.text(sql),
                query_file_md5=query_file_md5
            )
            for row in cursor:
                return row[0]
