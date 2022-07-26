import sqlalchemy

DATA_TYPE_TEXT = 'text'
DATA_TYPE_UNICODE = 'unicode'
DATA_TYPE_BOOLEAN = 'boolean'
DATA_TYPE_DATE = 'date'
DATA_TYPE_DATETIME = 'datetime'
DATA_TYPE_INTEGER = 'integer'
DATA_TYPE_JSON = 'json'

DATA_TYPES_TO_SQLALCHEMY_TYPES = {
    DATA_TYPE_TEXT: lambda collation: sqlalchemy.Text(),
    DATA_TYPE_UNICODE: lambda collation: sqlalchemy.UnicodeText(collation),
    DATA_TYPE_BOOLEAN: lambda _: sqlalchemy.Boolean(),
    DATA_TYPE_DATETIME: lambda _: sqlalchemy.DateTime(),
    DATA_TYPE_DATE: lambda _: sqlalchemy.Date(),
    DATA_TYPE_INTEGER: lambda _: sqlalchemy.Integer(),
    DATA_TYPE_JSON: lambda _: sqlalchemy.JSON(),
}


class UnknownDataType(Exception):
    pass


def get_sqlalchemy_type(data_type, collation):
    if data_type not in DATA_TYPES_TO_SQLALCHEMY_TYPES:
        raise UnknownDataType(data_type)
    else:
        return DATA_TYPES_TO_SQLALCHEMY_TYPES[data_type](collation)
