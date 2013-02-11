import re
import zipfile
from StringIO import StringIO
import csv
import json

from itertools import chain

MAX_COLUMN_SIZE = 2000

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
        for row in table:
            writer.writerow(map(_encode_if_needed(val) for val in row))

        self.archive.writestr('%s.csv' % self.zip_safe_name_for_table(name),
                              tempfile.value())

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.archive.close()
        self.file.seek(0)

    def zip_safe_name(name):
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

        sheet.append([unicode(v) for v in table['headings']])
        for row in table['rows']:
            sheet.append([unicode(v) for v in row])
        
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
                sheet.write(rownum, colnum, unicode(val))
        
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

