

class TableSpec:

    def __init__(self, name, headings, rows, data_types=None):
        self.name = name
        self.headings = headings
        self.rows = rows
        self.data_types = data_types or []

    def __eq__(self, other):
        return (
            isinstance(other, TableSpec)
            and other.name == self.name
            and other.headings == self.headings
            and other.data_types == self.data_types
        )

    def toJSON(self):
        return {
            'name': self.name,
            'headings': self.headings,
            'data_types': self.data_types,
        }
