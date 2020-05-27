

class TableSpec:

    def __init__(self, name, headings, rows):
        self.name = name
        self.headings = headings
        self.rows = rows

    def __eq__(self, other):
        return (
            isinstance(other, TableSpec) and
            other.name == self.name and
            other.headings == self.headings and
            other.rows == self.rows
        )

    def toJSON(self):
        return {
            'name': self.name,
            'headings': self.headings,
            'rows': self.rows,
        }
