import csv
import datetime
import logging
import sys
import zipfile
from itertools import chain

import alembic
import six
import sqlalchemy
from six import StringIO, u

logger = logging.getLogger(__name__)

MAX_COLUMN_SIZE = 2000


def ensure_text(v, convert_none=False):
    if v is None:
        return '' if convert_none else v

    if isinstance(v, six.text_type):
        return v
    elif isinstance(v, six.binary_type):
        return u(v)
    elif isinstance(v, datetime.datetime):
        return v.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(v, datetime.date):
        return v.isoformat()
    else:
        return u(str(v))

def to_jvalue(v):
    if v is None:
        return None

    if isinstance(v, (six.text_type,) + six.integer_types):
        return v
    elif isinstance(v, six.binary_type):
        return u(v)
    else:
        return u(str(v))

class TableWriter(object):
    """
    Interface for export writers: Usable in a "with"
    statement, and while open one can call write_table.

    If the implementing class does not actually need any
    set up, no-op defaults have been provided
    """
    max_column_length = None
    support_checkpoints = False

    # set to False if writer does not support writing to the same table multiple times
    supports_multi_table_write = True

    def __enter__(self):
        return self
    
    def write_table(self, table):
        "{'name': str, 'headings': [str], 'rows': [[str]]} -> ()"
        raise NotImplementedError()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class CsvTableWriter(TableWriter):
    supports_multi_table_write = False

    def __init__(self, file, max_column_size=MAX_COLUMN_SIZE):
        self.file = file
        self.tables = []
        self.archive = None
        
    def __enter__(self):
        self.archive = zipfile.ZipFile(self.file, 'w', zipfile.ZIP_DEFLATED)
        return self

    def write_table(self, table):
        if self.archive is None:
            raise Exception('Attempt to write to a closed CsvWriter')

        tempfile = StringIO()
        writer = csv.writer(tempfile, dialect=csv.excel)
        writer.writerow(table['headings'])
        for row in table['rows']:
            writer.writerow([val.encode('utf-8') if isinstance(val, six.text_type) else val
                             for val in row])

        # TODO: make this a polite zip and put everything in a subfolder with the same basename
        # as the zipfile
        self.archive.writestr('%s.csv' % self.zip_safe_name(table['name']),
                              tempfile.getvalue())

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.archive.close()

    def zip_safe_name(self, name):
        return name[:31]


class Excel2007TableWriter(TableWriter):
    max_table_name_size = 31
    
    def __init__(self, file):
        try:
            import openpyxl
        except ImportError:
            raise Exception("It doesn't look like this machine is configured for "
                            "excel export. To export to excel you have to run the "
                            "command:  pip install openpyxl")

        self.file = file
        self.book = openpyxl.workbook.Workbook(optimized_write=True)
        self.sheets = {}

    def __enter__(self):
        return self

    def write_table(self, table):
        sheet = self.get_sheet(table)
        for row in table['rows']:
            sheet.append([ensure_text(v) for v in row])

    def get_sheet(self, table):
        name = table['name']
        if name not in self.sheets:
            sheet = self.book.create_sheet()
            sheet.title = name[:self.max_table_name_size]
            sheet.append([ensure_text(v) for v in table['headings']])
            self.sheets[name] = sheet

        return self.sheets[name]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.book.save(self.file)


class Excel2003TableWriter(TableWriter):
    max_table_name_size = 31

    def __init__(self, file):
        try:
            import xlwt
        except ImportError:
            raise Exception("It doesn't look like this machine is configured for "
                            "excel export. To export to excel you have to run the "
                            "command:  pip install xlwt")

        self.file = file
        self.book = xlwt.Workbook()
        self.sheets = {}

    def __enter__(self):
        return self

    def write_table(self, table):
        sheet, current_row = self.get_sheet(table)
        for row in table['rows']:
            for colnum, val in enumerate(row):
                sheet.write(current_row, colnum, ensure_text(val))
            current_row += 1

        self.sheets[table['name']] = (sheet, current_row)

    def get_sheet(self, table):
        name = table['name']
        if name not in self.sheets:
            sheet = self.book.add_sheet(name[:self.max_table_name_size])
            sheet.title = name[:self.max_table_name_size]

            for colnum, val in enumerate(table['headings']):
                sheet.write(0, colnum, ensure_text(val))

            self.sheets[name] = (sheet, 1) # start from row 1

        return self.sheets[name]
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.book.save(self.file)


class JValueTableWriter(TableWriter):
    """
    Write tables to JSON-friendly in-memory values
    """

    def __init__(self):
        self.tables = {}
    
    def write_table(self, table):
        if table['name'] not in self.tables:
            self.tables[table['name']] = {
                'name': table['name'],
                'headings': list(table['headings']),
                'rows': []
            }
        else:
            assert self.tables[table['name']]['headings'] == list(table['headings'])

        self.tables[table['name']]['rows'].extend(
            [[to_jvalue(v) for v in row] for row in table['rows']]
        )


class StreamingMarkdownTableWriter(TableWriter):
    """
    Writes markdown to an output stream, where each table just comes one after the other
    """
    supports_multi_table_write = False

    def __init__(self, output_stream, compute_widths=False):
        self.output_stream = output_stream
        self.compute_widths = compute_widths
    
    def write_table(self, table, ):
        col_widths = None
        if self.compute_widths:
            col_widths = self._get_column_widths(table)
            row_template = ' | '.join(['{{:<{}}}'.format(width) for width in col_widths])
        else:
            row_template = ' | '.join(['{}'] * len(table['headings']))

        if table.get('name'):
            self.output_stream.write('\n# %s \n\n' % table['name'])

        self.output_stream.write('| %s |\n' % row_template.format(*table['headings']))
        if col_widths:
            self.output_stream.write('| %s |\n' % row_template.format(*['-' * width for width in col_widths]))

        for row in table['rows']:
            text_row = (ensure_text(val, convert_none=True) for val in row)
            self.output_stream.write('| %s |\n' % row_template.format(*text_row))

    def _get_column_widths(self, table):
        all_rows = [table['headings']] + table['rows']
        columns = list(map(list, zip(*all_rows)))
        col_widths = map(len, [max(col, key=len) for col in columns])
        return col_widths


class SqlMixin(object):
    """
    Write tables to a database specified by URL
    (TODO) with "upsert" based on primary key.
    """

    MIN_VARCHAR_LEN = 32
    MAX_VARCHAR_LEN = 255  # Arbitrary point at which we switch to TEXT; for postgres VARCHAR == TEXT anyhow

    def __init__(self, db_url, poolclass=None):
        self.db_url = db_url
        self.collation = 'utf8_bin' if 'mysql' in db_url else None
        self.engine = sqlalchemy.create_engine(db_url, poolclass=poolclass)

    def __enter__(self):
        self.connection = self.engine.connect()
        return self  # TODO: fork the writer so this can be called many times

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()

    @property
    def max_column_length(self):
        if 'postgres' in self.db_url:
            # https://www.postgresql.org/docs/current/static/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
            return 63
        if 'mysql' in self.db_url:
            # https://dev.mysql.com/doc/refman/8.0/en/identifiers.html
            return 64
        if 'mssql' in self.db_url:
            # https://docs.microsoft.com/en-us/sql/relational-databases/databases/database-identifiers?view=sql-server-2017
            return 128
        raise Exception("Unknown database dialect: {}".format(self.db_url))

    @property
    def metadata(self):
        if not hasattr(self, '_metadata') or self._metadata.bind.closed or self._metadata.bind.invalidated:
            if self.connection.closed:
                raise Exception('Tried to reflect via a closed connection')
            if self.connection.invalidated:
                raise Exception('Tried to reflect via an invalidated connection')
            self._metadata = sqlalchemy.MetaData()
            self._metadata.bind = self.connection
            self._metadata.reflect()
        return self._metadata

    def table(self, table_name):
        return sqlalchemy.Table(table_name, self.metadata, autoload=True, autoload_with=self.connection)

    def get_id_column(self):
        return sqlalchemy.Column(
            'id',
            sqlalchemy.Unicode(self.MAX_VARCHAR_LEN),
            primary_key=True
        )


class SqlTableWriter(SqlMixin, TableWriter):
    """
    Write tables to a database specified by URL
    (TODO) with "upsert" based on primary key.
    """
    support_checkpoints = True

    def __init__(self, db_url, strict_types=False, poolclass=None):
        super(SqlTableWriter, self).__init__(db_url, poolclass=poolclass)
        self.strict_types = strict_types

    def best_type_for(self, val):
        if isinstance(val, bool):
            return sqlalchemy.Boolean()
        elif isinstance(val, datetime.datetime):
            return sqlalchemy.DateTime()
        elif isinstance(val, datetime.date):
            return sqlalchemy.Date()

        if isinstance(val, int):
            return sqlalchemy.Integer()
        elif isinstance(val, six.string_types):
            # Notes on the conversions between various string types:
            # 1. PostgreSQL is the best; you can use TEXT everywhere and it works like a charm.
            # 2. MySQL cannot build an index on TEXT due to the lack of a field length, so we
            #    try to use VARCHAR when possible.
            if len(val) < self.MAX_VARCHAR_LEN: # FIXME: Is 255 an interesting cutoff?
                return sqlalchemy.Unicode( max(len(val), self.MIN_VARCHAR_LEN), collation=self.collation)
            else:
                return sqlalchemy.UnicodeText(collation=self.collation)
        else:
            # We do not have a name for "bottom" in SQL aka the type whose least upper bound
            # with any other type is the other type.
            return sqlalchemy.UnicodeText(collation=self.collation)

    def compatible(self, source_type, dest_type):
        """
        Checks _coercion_ compatibility.
        """
        if isinstance(source_type, sqlalchemy.String):
            if not isinstance(dest_type, sqlalchemy.String):
                return False
            elif source_type.length is None:
                # The length being None means that we are looking at indefinite strings aka TEXT.
                # This tool will never create strings with bounds, but if a target DB has one then
                # we cannot insert to it.
                # We will request that whomever uses this tool convert to TEXT type.
                return dest_type.length is None
            else:
                return dest_type.length is None or (dest_type.length >= source_type.length)

        compatibility = {
            sqlalchemy.String: (sqlalchemy.Text,),
            sqlalchemy.Integer: (sqlalchemy.String, sqlalchemy.Text),
            sqlalchemy.Boolean: (sqlalchemy.String, sqlalchemy.Text, sqlalchemy.Integer),
            sqlalchemy.DateTime: (sqlalchemy.String, sqlalchemy.Text, sqlalchemy.Date),
            sqlalchemy.Date: (sqlalchemy.String, sqlalchemy.Text),
        }

        # add dialect specific types
        try:
            compatibility[sqlalchemy.Boolean] += (sqlalchemy.dialects.mssql.base.BIT,)
        except AttributeError:
            pass

        for _type, types in compatibility.items():
            if isinstance(source_type, _type):
                return isinstance(dest_type, (_type,) + types)

    def strict_types_compatibility_check(self, source_type, dest_type):
        if isinstance(source_type, sqlalchemy.String):
            if not isinstance(dest_type, sqlalchemy.String):
                return  # Can't do anything
            elif dest_type.length is None:
                # already a TEXT column
                return
            elif source_type.length is None:
                return sqlalchemy.UnicodeText(collation=self.collation)
            elif dest_type.length < source_type.length:
                return source_type

    def least_upper_bound(self, source_type, dest_type):
        """
        Returns the _coercion_ least uppper bound. 
        Mostly just promotes everything to string if it is not already.
        In fact, since this is only called when they are incompatible, it promotes to string right away.
        """

        # FIXME: Don't be so silly
        return sqlalchemy.UnicodeText(collation=self.collation)

    def make_table_compatible(self, table_name, row_dict):
        ctx = alembic.migration.MigrationContext.configure(self.connection)
        op = alembic.operations.Operations(ctx)

        if not table_name in self.metadata.tables:
            def get_columns():
                return [self.get_id_column()] + [
                    sqlalchemy.Column(name, self.best_type_for(val), nullable=True)
                    for name, val in row_dict.items() if val is not None and name != 'id'
                ]

            if self.strict_types:
                create_sql = sqlalchemy.schema.CreateTable(sqlalchemy.Table(
                    table_name,
                    sqlalchemy.MetaData(),
                    *get_columns()
                )).compile(self.connection.engine)
                logger.warn("Table '{table_name}' does not exist. Creating table with:\n{schema}".format(
                    table_name=table_name,
                    schema=create_sql
                ))
                empty_cols = [name for name, val in row_dict.items() if val is None]
                if empty_cols:
                    logger.warn("This schema does not include the following columns since we are unable "
                                "to determine the column type at this stage: {}".format(empty_cols))
            op.create_table(table_name, *get_columns())
            self.metadata.clear()
            self.metadata.reflect()
            return

        def get_cols():
            return {c.name: c for c in self.table(table_name).columns}

        columns = get_cols()

        for column, val in row_dict.items():
            if val is None:
                continue

            ty = self.best_type_for(val)
            if not column in columns:
                logger.warn("Adding column '{}.{} {}'".format(table_name, column, ty))
                op.add_column(table_name, sqlalchemy.Column(column, ty, nullable=True))
                self.metadata.clear()
                self.metadata.reflect()
                columns = get_cols()
            else:
                current_ty = columns[column].type
                new_type = None
                if self.strict_types:
                    # don't bother checking compatibility since we're not going to change anything
                    new_type = self.strict_types_compatibility_check(ty, current_ty)
                elif not self.compatible(ty, current_ty):
                    new_type = self.least_upper_bound(ty, current_ty)

                if new_type:
                    logger.warn('Altering column %s from %s to %s for value: "%s:%s"', columns[column], current_ty, new_type, type(val), val)
                    op.alter_column(table_name, column, type_=new_type)
                    self.metadata.clear()
                    self.metadata.reflect()
                    columns = get_cols()

    def upsert(self, table, row_dict):
        # For atomicity "insert, catch, update" is slightly better than "select, insert or update".
        # The latter may crash, while the former may overwrite data (which should be fine if whatever is
        # racing against this is importing from the same source... if not you are busted anyhow

        # strip out values that are None since the column may not exist yet
        row_dict = {col: val for col, val in row_dict.items() if val is not None}
        try:
            insert = table.insert().values(**row_dict)
            self.connection.execute(insert)
        except sqlalchemy.exc.IntegrityError:
            update = table.update().where(table.c.id == row_dict['id']).values(**row_dict)
            self.connection.execute(update)

    def write_table(self, table):
        """
        :param table: dict of {'name': 'name', 'headings', [...], 'rows': [[...], [...]]
        """
        table_name = table['name']
        headings = table['headings']

        # Rather inefficient for now...
        for row in table['rows']:
            if logger.getEffectiveLevel() == logging.DEBUG: sys.stderr.write('.')

            row_dict = dict(zip(headings, row))
            self.make_table_compatible(table_name, row_dict)
            self.upsert(self.table(table_name), row_dict)

        if logger.getEffectiveLevel() == 'DEBUG': sys.stderr.write('\n')
