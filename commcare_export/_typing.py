from collections.abc import Callable
from functools import partial
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column


# Typed SQLAlchemy column functions make model definitions more readable
optional_bool_column: Callable[..., Mapped[Optional[bool]]] = partial(mapped_column, Boolean)
optional_string_column: Callable[..., Mapped[Optional[str]]] = partial(mapped_column, String)
string_column: Callable[..., Mapped[str]] = partial(mapped_column, String)
