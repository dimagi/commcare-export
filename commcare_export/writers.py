import re
import sys
import zipfile
import csv
import json
import logging

import six
from six import StringIO, u

from itertools import chain

logger = logging.getLogger(__name__)

MAX_COLUMN_SIZE = 2000

def ensure_text(v):
    if isinstance(v, six.text_type):
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

    def __enter__(self):
        return self
    
    def write_table(self, table):
        "{'name': str, 'headings': [str], 'rows': [[str]]} -> ()"
        raise NotImplementedError() 

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class CsvTableWriter(TableWriter):
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

    def __enter__(self):
        return self

    def write_table(self, table):
        sheet = self.book.create_sheet()
        sheet.title = table['name'][:self.max_table_name_size]

        sheet.append([ensure_text(v) for v in table['headings']])
        for row in table['rows']:
            sheet.append([ensure_text(v) for v in row])
        
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

    def __enter__(self):
        return self

    def write_table(self, table):
        sheet = self.book.add_sheet(table['name'][:self.max_table_name_size])

        for rownum, row in enumerate(chain([table['headings']], table['rows'])):
            for colnum, val in enumerate(row):
                sheet.write(rownum, colnum, ensure_text(val))
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.book.save(self.file)

class JValueTableWriter(TableWriter):
    """
    Write tables to JSON-friendly in-memory values
    """

    def __init__(self):
        self.tables = []
    
    def write_table(self, table):
        # Ensures the table is iterable; probably better to create a custom JSON handler that runs in constant space
        self.tables.append(dict(name=table['name'],
                                headings=list(table['headings']),
                                rows=[list(row) for row in table['rows']]))

class StreamingMarkdownTableWriter(TableWriter):
    """
    Writes markdown to an output stream, where each table just comes one after the other
    """

    def __init__(self, output_stream):
        self.output_stream = output_stream
    
    def write_table(self, table):
        self.output_stream.write('\n# %s \n\n' % table['name'])
        self.output_stream.write('|%s|\n' % '|'.join(table['headings']))

        for row in table['rows']:
            self.output_stream.write('|%s|\n' % '|'.join(row))

class SqlTableWriter(TableWriter):
    """
    Write tables to a database specified by URL
    (TODO) with "upsert" based on primary key.
    """

    MIN_VARCHAR_LEN=32  # Since SQLite does not actually support ALTER COLUMN type, let's maximize the chance that we do not have to write workarounds by starting medium
    MAX_VARCHAR_LEN=255 # Arbitrary point at which we switch to TEXT; for postgres VARCHAR == TEXT anyhow and for Sqlite it doesn't matter either

    def __init__(self, connection):
        try:
            import sqlalchemy
            import alembic
            self.sqlalchemy = sqlalchemy
            self.alembic = alembic
        except ImportError:
            raise Exception("It doesn't look like this machine is configured for "
                            "SQL export. To export to SQL you have to run the "
                            "command:  pip install sqlalchemy alembic")

        self.base_connection = connection

    def __enter__(self):
        self.connection = self.base_connection.connect() # "forks" the SqlAlchemy connection
        return self # TODO: fork the writer so this can be called many times

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()

    @property
    def metadata(self):
        if not hasattr(self, '_metadata') or self._metadata.bind.closed or self._metadata.bind.invalidated:
            if self.connection.closed:
                raise Exception('Tried to reflect via a closed connection')
            if self.connection.invalidated:
                raise Exception('Tried to reflect via an invalidated connection')
            self._metadata = self.sqlalchemy.MetaData()
            self._metadata.bind = self.connection
            self._metadata.reflect()
        return self._metadata

    def table(self, table_name):
        return self.sqlalchemy.Table(table_name, self.metadata, autoload=True, autoload_with=self.connection)

    def best_type_for(self, val):
        if isinstance(val, int):
            return self.sqlalchemy.Integer()
        elif isinstance(val, six.string_types):
            # Notes on the conversions between various string types:
            # 1. PostgreSQL is the best; you can use TEXT everywhere and it works like a charm.
            # 2. MySQL cannot build an index on TEXT due to the lack of a field length, so we
            #    try to use VARCHAR when possible.
            # 3. But SQLite really barfs on altering columns. Luckily it does actually have real types,
            #    so we count on other parts of this code to not bother running column alterations
            if len(val) < self.MAX_VARCHAR_LEN: # FIXME: Is 255 an interesting cutoff?
                return self.sqlalchemy.Unicode( max(len(val), self.MIN_VARCHAR_LEN) )
            else:
                return self.sqlalchemy.UnicodeText()
        else:
            # We do not have a name for "bottom" in SQL aka the type whose least upper bound
            # with any other type is the other type.
            return None

    def compatible(self, source_type, dest_type):
        """
        Checks _coercion_ compatibility.
        """

        # FIXME: Add datetime and friends
        if isinstance(source_type, self.sqlalchemy.Integer):
            # Integers can be cast to varch
            return True

        if isinstance(source_type, self.sqlalchemy.String):
            if not isinstance(dest_type, self.sqlalchemy.String):
                False
            elif source_type.length is None:
                # The length being None means that we are looking at indefinite strings aka TEXT.
                # This tool will never create strings with bounds, but if a target DB has one then
                # we cannot insert to it.
                # We will request that whomever uses this tool convert to TEXT type.
                return dest_type.length is None
            else:
                return (dest_type.length >= source_type.length)

    def least_upper_bound(self, source_type, dest_type):
        """
        Returns the _coercion_ least uppper bound. 
        Mostly just promotes everything to string if it is not already.
        In fact, since this is only called when they are incompatible, it promotes to string right away.
        """

        # FIXME: Don't be so silly
        return self.sqlalchemy.UnicodeText()

    def make_table_compatible(self, table_name, row_dict):
        # FIXME: This does lots of redundant checks in a tight loop. Stop doing that.
        
        ctx = self.alembic.migration.MigrationContext.configure(self.connection)
        op = self.alembic.operations.Operations(ctx)

        if not table_name in self.metadata.tables:
            id_column = self.sqlalchemy.Column(
                'id',
                self.sqlalchemy.Unicode(self.MAX_VARCHAR_LEN),
                primary_key=True
            )
            op.create_table(table_name, id_column)
            self.metadata.reflect()

        for column, val in row_dict.items():
            ty = self.best_type_for(val)

            if not column in [c.name for c in self.table(table_name).columns]:
                # If we are creating the column, a None crashes things even though it is the "empty" type
                # but SQL does not have such a type. So we have to guess a liberal type for future use.
                ty = ty or self.sqlalchemy.UnicodeText()
                op.add_column(table_name, self.sqlalchemy.Column(column, ty, nullable=True))
                self.metadata.clear()
                self.metadata.reflect()

            else:
                columns = dict([(c.name, c) for c in self.table(table_name).columns])
                current_ty = columns[column].type

                if not self.compatible(ty, current_ty) and not ('sqlite' in self.connection.engine.driver):
                    op.alter_column(table_name, column, type_ = self.least_upper_bound(current_ty, ty))
                    self.metadata.clear()
                    self.metadata.reflect()

    def upsert(self, table, row_dict):

        # For atomicity "insert, catch, update" is slightly better than "select, insert or update".
        # The latter may crash, while the former may overwrite data (which should be fine if whatever is
        # racing against this is importing from the same source... if not you are busted anyhow
        try:
            insert = table.insert().values(**row_dict)
            self.connection.execute(insert)
        except self.sqlalchemy.exc.IntegrityError:
            update = table.update().where(table.c.id == row_dict['id']).values(**row_dict)
            self.connection.execute(update)

    def write_table(self, table):
        table_name = table['name']
        headings = table['headings']

        # Rather inefficient for now...
        for row in table['rows']:
            if logger.getEffectiveLevel() == logging.DEBUG: sys.stderr.write('.')

            row_dict = dict(zip(headings, row))
            self.make_table_compatible(table_name, row_dict)
            self.upsert(self.table(table_name), row_dict)

        if logger.getEffectiveLevel() == 'DEBUG': sys.stderr.write('\n')
        
