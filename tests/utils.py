from commcare_export.writers import SqlTableWriter
from sqlalchemy import text


class SqlWriterWithTearDown(SqlTableWriter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tables = set()

    def write_table(self, table_spec):
        super().write_table(table_spec)
        if table_spec.rows:
            self.tables.add(table_spec.name)

    def tear_down(self):
        for table in self.tables:
            self.engine.execute(text(f'DROP TABLE "{table}"'))
        self.tables = set()
