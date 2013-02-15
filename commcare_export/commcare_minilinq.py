"""
CommCare/Export-specific extensions to MiniLinq. 
"""

from minilinq import *
    
class ApiQuery(MiniLinq):
    """
    This MiniLinq writes a whole table to whatever writer is registered in the `env`.
    In practice,  a table to a dict of a name, headers, and rows, so the
    writer is free to do an idempotent upsert, etc.

    Note that it does not actually check that the number of headings is
    correct, nor does it try to ensure that the things being emitted
    are actually lists - it is just crashy instead.
    """
    def __init__(self, table, headings, source):
        "(str, [(str, MiniLinq)]) -> MiniLinq"
        self.table = table
        self.headings = headings
        self.source = source

    def coerce_cell(self, cell):
        if isinstance(cell, unicode):
            return cell
        elif isinstance(cell, str):
            return unicode(cell)
        elif isinstance(cell, int):
            return cell
        elif isinstance(cell, datetime):
            return cell

        # In all other cases, coerce to a list and join with ',' for now
        return ','.join([self.coerce_cell(item) for item in list(cell)])
        
    def coerce_row(self, row):
        return [self.coerce_cell(cell) for cell in row]

    def eval(self, env):
        rows = self.source.eval(env)
        env.emit_table({'name': self.table,
                        'headings': [heading.eval(env) for heading in self.headings],
                        'rows': imap(self.coerce_row, rows)})
        return rows

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Emit']

        return cls(table    = fields['table'],
                   source   = MiniLinq.from_jvalue(fields['source']),
                   headings = [MiniLinq.from_jvalue(heading) for heading in fields['headings']])

    def to_jvalue(self):
        return {'Emit': {'table': self.table,
                         'headings': [heading.to_jvalue() for heading in self.headings],
                         'source': self.source.to_jvalue()}}
