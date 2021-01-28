from commcare_export.writers import SqlTableWriter


class SqlWriterWithTearDown(SqlTableWriter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tables = set()

    def write_table(self, table):
        super().write_table(table)
        if table.rows:
            self.tables.add(table.name)

    def tear_down(self):
        for table in self.tables:
            self.engine.execute(f'DROP TABLE "{table}"')
        self.tables = set()
