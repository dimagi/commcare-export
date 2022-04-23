class DataExportException(Exception):
    message = None


class LongFieldsException(DataExportException):

    def __init__(self, long_fields, max_length):
        self.long_fields = long_fields
        self.max_length = max_length

    @property
    def message(self):
        message = ''
        for table, headers in self.long_fields.items():
            message += (
                f'Table "{table}" has field names longer than the maximum '
                f'allowed for this database ({self.max_length}):\n'
            )
            for header in headers:
                message += '    {}\n'.format(header)

        message += (
            '\nPlease adjust field names to be within the maximum length '
            f'limit of {self.max_length}'
        )
        return message


class MissingColumnException(DataExportException):

    def __init__(self, errors_by_sheet):
        self.errors_by_sheet = errors_by_sheet

    @property
    def message(self):
        lines = [
            'Sheet "{}" is missing definitions for required fields: "{}"'
            .format(sheet, '", "'.join(missing_cols))
            for (sheet, missing_cols) in self.errors_by_sheet.items()
        ]
        return '\n'.join(lines)


class MissingQueryFileException(DataExportException):

    def __init__(self, query_file):
        self.query_file = query_file

    @property
    def message(self):
        return f'Query file not found: {self.query_file}'


class ReservedTableNameException(DataExportException):

    def __init__(self, conflicting_name):
        self.conflicting_name = conflicting_name

    @property
    def message(self):
        return (
            f'Table name "{self.conflicting_name}" conflicts with an internal '
            f'table name. Please export to a different table.'
        )
