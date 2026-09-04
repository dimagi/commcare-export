class DataExportException(Exception):
    @property
    def message(self):
        # subclasses either pass a finished message to __init__ or
        # override this property
        return str(self)


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
                message += f'    {header}\n'

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
            f'Sheet "{sheet}" is missing definitions for required fields: "{", ".join(missing_cols)}"'
            for (sheet, missing_cols) in self.errors_by_sheet.items()
        ]
        return '\n'.join(lines)


class MissingQueryFileException(DataExportException):

    def __init__(self, query_file):
        self.query_file = query_file

    @property
    def message(self):
        return f'Query file not found: {self.query_file}'


def truncated(text, limit=100):
    # exported values can carry sensitive data and forged log lines, so
    # neutralize control characters and cap what exceptions carry into
    # error messages and logs
    text = ''.join(
        char if char.isprintable() else ' ' for char in str(text)
    )
    return text if len(text) <= limit else text[:limit] + '...'


class DeltaWriteException(DataExportException):

    def __init__(self, table, reason):
        super().__init__(
            f'Error writing table "{truncated(table, 50)}": '
            f'{truncated(reason)}'
        )


class UnwritableValueException(DataExportException):

    def __init__(self, table, column, value, error, row_id=None):
        for_row = (
            f' for row id {truncated(repr(row_id), 50)}'
            if row_id is not None else ''
        )
        super().__init__(
            f'Cannot write value {truncated(repr(value), 50)} to column '
            f'"{truncated(column, 50)}" of table "{truncated(table, 50)}"'
            f'{for_row}: {truncated(error)}'
        )


class ReservedTableNameException(DataExportException):

    def __init__(self, conflicting_name):
        self.conflicting_name = conflicting_name

    @property
    def message(self):
        return (
            f'Table name "{self.conflicting_name}" conflicts with an internal '
            f'table name. Please export to a different table.'
        )
