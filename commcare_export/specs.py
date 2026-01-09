from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


@dataclass
class TableSpec:
    name: str
    headings: list[str]
    rows: Iterable[list[Any]]  # Generator for lazy evaluation
    data_types: list[Optional[str]] = field(default_factory=list)

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
