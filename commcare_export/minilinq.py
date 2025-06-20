from typing import Any, Dict
from typing import List as ListType
from typing import Optional

from commcare_export.env import Env
from commcare_export.misc import unwrap, unwrap_val
from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.specs import TableSpec
from commcare_export import get_logger

logger = get_logger(__file__)


class MiniLinq:
    """
    The abstract base class for MiniLinqs, and also the factory/registry
    for dispatching parsing, etc.
    """

    def eval(self, env: Env) -> Any:
        raise NotImplementedError()

    #### Factory methods ####

    _node_classes: Dict[str, 'MiniLinq'] = {}

    @classmethod
    def register(cls, clazz, slug=None):
        cls._node_classes[slug or clazz.__name__] = clazz

    @classmethod
    def from_jvalue(cls, jvalue):
        """
        The term `jvalue` is code for "the output of a JSON
        deserialization". This  module does not actually care about
        JSON, which is concrete syntax, but  only the corresponding data
        model of lists and string-indexed dictionaries.

        (since this data might never actually be a string, that layer is
        handled elsewhere)
        """

        # This is a bit wonky, but this method really should not be
        # inherited. So if we end up here from a subclass, it is broken.
        if not issubclass(MiniLinq, cls):
            raise NotImplementedError()

        if isinstance(jvalue, str):
            return jvalue

        elif isinstance(jvalue, list):
            # Leverage for literal lists of data in the code
            return [MiniLinq.from_jvalue(v) for v in jvalue]

        elif isinstance(jvalue, dict):
            # Dictionaries are reserved; they must always have exactly
            # one entry and it must be the AST node class
            if len(jvalue.values()) != 1:
                raise ValueError(
                    'JValue serialization of AST contains dict with number of slugs != 1'
                )
            slug = list(jvalue.keys())[0]

            if slug not in cls._node_classes:
                raise ValueError(
                    f'JValue serialization of AST contains unknown node type: {slug}'
                )

            return cls._node_classes[slug].from_jvalue(jvalue)

    def to_jvalue(self):
        raise NotImplementedError()


class Reference(MiniLinq):
    """
    An MiniLinq referencing a datum or data. It is flexible about what
    the type of the environment is, but it must support using these as
    keys.
    """

    def __init__(self, ref):
        self.ref = ref  #parse_jsonpath(ref) #ref
        self.nested = isinstance(self.ref, MiniLinq)

    def eval(self, env):
        if self.nested:
            ref = self.ref.eval(env)
            return env.lookup(ref)
        return env.lookup(self.ref)

    def __eq__(self, other):
        return isinstance(other, Reference) and self.ref == other.ref

    @classmethod
    def from_jvalue(cls, jvalue):
        return cls(MiniLinq.from_jvalue(jvalue['Ref']))

    def to_jvalue(self):
        return {'Ref': self.ref.to_jvalue() if self.nested else self.ref}

    def __repr__(self):
        return f'{self.__class__.__name__}({self.ref!r})'


class Literal(MiniLinq):
    """
    An MiniLinq wrapper around a python value. Returns exactly the value
    given to it. Note: when going to/from jvalue the contents are left
    alone, so it can be _used_ with a non-JSON encodable value, but
    cannot be encoded.
    """

    def __init__(self, v):
        self.v = v

    def eval(self, env):
        return self.v

    def __eq__(self, other):
        return isinstance(other, Literal) and self.v == other.v

    def __repr__(self):
        return f'{self.__class__.__name__}({self.v!r})'

    @classmethod
    def from_jvalue(cls, jvalue):
        return cls(jvalue['Lit'])

    def to_jvalue(self):
        return {'Lit': self.v}


class Bind(MiniLinq):
    """
    Binds the results of an expression to a new name. Will be useful in
    writing exports by hand or debugging, and maybe for efficiency if it
    de-dupes computation (but generally exports will be expected to be
    too large to store, so it'll be re-run on each access.
    """

    def __init__(self, name: str, value: MiniLinq, body: MiniLinq) -> None:
        self.name = name
        self.value = value
        self.body = body

    def eval(self, env):
        return self.body.eval(env.bind(self.name, self.value.eval(env)))

    def __eq__(self, other):
        return isinstance(
            other, Bind
        ) and self.name == other.name and self.value == other.value and self.body == other.body

    def __repr__(self):
        return (
            f'{self.__class__.__name__}'
            f'(name={self.name!r}, '
            f'value={self.value!r}, '
            f'body={self.body!r})'
        )

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Bind']
        return cls(
            name=fields['name'],
            value=MiniLinq.from_jvalue(fields['value']),
            body=MiniLinq.from_jvalue(fields['body'])
        )

    def to_jvalue(self):
        return {
            'Bind': {
                'name': self.name,
                'value': self.value.to_jvalue(),
                'body': self.body.to_jvalue()
            }
        }


class Filter(MiniLinq):
    """
    Just what it sounds like
    """

    def __init__(
        self,
        source: MiniLinq,
        predicate: MiniLinq,
        name: Optional[str] = None
    ) -> None:
        self.source = source
        self.name = name
        self.predicate = predicate

    def eval(self, env):
        source_result = self.source.eval(env)

        # Python closure workaround
        def iterate(
            env_=env,
            source_result_=source_result,
        ):
            if self.name:
                for item in source_result_:
                    if self.predicate.eval(env_.bind(self.name, item)):
                        yield item
            else:
                for item in source_result_:
                    if self.predicate.eval(env_.replace(item)):
                        yield item

        return RepeatableIterator(iterate)

    def __eq__(self, other):
        return (
            isinstance(other, Filter) and self.source == other.source
            and self.name == other.name and self.predicate == other.predicate
        )

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Filter']

        # TODO: catch errors and give informative error messages
        return cls(
            predicate=MiniLinq.from_jvalue(fields['predicate']),
            source=MiniLinq.from_jvalue(fields['source']),
            name=fields.get('name')
        )

    def to_jvalue(self):
        return {
            'Filter': {
                'predicate': self.predicate.to_jvalue(),
                'source': self.source.to_jvalue(),
                'name': self.name
            }
        }

    def __repr__(self):
        return (
            f'{self.__class__.__name__}'
            f'(source={self.source!r}, '
            f'name={self.name!r}, '
            f'predicate={self.predicate!r})'
        )


class List(MiniLinq):
    """
    A list of expressions, embeds the [ ... ] syntax into the MiniLinq
    meta-leval
    """

    def __init__(self, items):
        self.items = items

    def eval(self, env):
        return [item.eval(env) for item in self.items]

    def __eq__(self, other):
        return isinstance(other, List) and self.items == other.items

    def __repr__(self):
        return f'{self.__class__.__name__}({self.items})'

    @classmethod
    def from_jvalue(cls, jvalue):
        return cls([MiniLinq.from_jvalue(item) for item in jvalue['List']])

    def to_jvalue(self):
        return {'List': [item.to_jvalue() for item in self.items]}


class Map(MiniLinq):
    """
    Like the `FROM` clause of a SQL `SELECT` or jQuery's map, binds each
    item from its `source` and evaluates the body MiniLinq.

    If `name` is provided to the constructor, then instead of replacing
    the environment with each row, it will just bind the row to `name`,
    enabling references to the rest of the env.
    """

    def __init__(
        self,
        source: MiniLinq,
        body: MiniLinq,
        name: Optional[str] = None
    ) -> None:
        self.source = source
        self.name = name
        self.body = body

    def eval(self, env):
        source_result = self.source.eval(env)

        def iterate(
            env=env, source_result=source_result
        ):  # Python closure workaround
            if self.name:
                for item in source_result:
                    yield self.body.eval(env.bind(self.name, item))
            else:
                for item in source_result:
                    yield self.body.eval(env.replace(item))

        return RepeatableIterator(iterate)

    def __eq__(self, other):
        return (
            isinstance(other, Map) and self.name == other.name
            and self.source == other.source and self.body == other.body
        )

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Map']

        # TODO: catch errors and give informative error messages
        return cls(
            body=MiniLinq.from_jvalue(fields['body']),
            source=MiniLinq.from_jvalue(fields['source']),
            name=fields.get('name')
        )

    def to_jvalue(self):
        return {
            'Map': {
                'body': self.body.to_jvalue(),
                'source': self.source.to_jvalue(),
                'name': self.name
            }
        }


class FlatMap(MiniLinq):
    """
    Somewhat like a JOIN, but not quite. Called `SelectMany` in LINQ and
    `flatMap` other languages. Obvious equivalence: `flatMap f = flatten
    . map f` but so common it is useful to have around.

    If `name` is provided to the constructor, then instead of replacing
    the environment with each row, it will just bind the row to `name`,
    enabling references to the rest of the env.
    """

    def __init__(
        self,
        source: MiniLinq,
        body: MiniLinq,
        name: Optional[str] = None
    ) -> None:
        self.source = source
        self.name = name
        self.body = body

    def eval(self, env):
        source_result = self.source.eval(env)

        # Python closure workaround
        def iterate(
            env_=env,
            source_result_=source_result,
        ):
            if self.name:
                for item in source_result_:
                    for result_item in self.body.eval(
                        env_.bind(self.name, item)
                    ):
                        yield result_item
            else:
                for item in source_result_:
                    for result_item in self.body.eval(env_.replace(item)):
                        yield result_item

        return RepeatableIterator(iterate)

    def __eq__(self, other):
        return (
            isinstance(other, FlatMap) and self.name == other.name
            and self.source == other.source and self.body == other.body
        )

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['FlatMap']

        # TODO: catch errors and give informative error messages
        return cls(
            body=MiniLinq.from_jvalue(fields['body']),
            source=MiniLinq.from_jvalue(fields['source']),
            name=fields.get('name')
        )

    def to_jvalue(self):
        return {
            'FlatMap': {
                'body': self.body.to_jvalue(),
                'source': self.source.to_jvalue(),
                'name': self.name
            }
        }


class Apply(MiniLinq):
    """
    Abstract syntax for function or operator application.
    """

    def __init__(self, fn, *args):
        self.fn = fn
        self.args = args

    def eval(self, env):
        fn_result = self.fn.eval(env)
        args_results = [arg.eval(env) for arg in self.args]

        try:
            result = fn_result(*args_results)
            if isinstance(result, MiniLinq):
                return result.eval(env)
        except Exception as e:
            args = ', '.join([str(unwrap_val(arg)) for arg in args_results])
            try:
                doc_id = unwrap_val(Reference('id').eval(env))
            except:
                doc_id = 'unknown'

            message = e.args[0] + (
                f": Error processing document '{doc_id}'. Failure to "
                f"evaluating expression '{self!r}' with arguments '{args}'"
            )

            e.args = (message,) + e.args[1:]
            raise
        return result

    def __eq__(self, other):
        return (
            isinstance(other, Apply) and self.fn == other.fn
            and self.args == other.args
        )

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Apply']

        # TODO: catch errors and give informative error messages
        return cls(
            MiniLinq.from_jvalue(fields['fn']),
            *[MiniLinq.from_jvalue(arg) for arg in fields['args']]
        )

    def to_jvalue(self):
        return {
            'Apply': {
                'fn': self.fn.to_jvalue(),
                'args': [arg.to_jvalue() for arg in self.args]
            }
        }

    def __repr__(self):
        return f'{self.__class__.__name__}({self.fn!r}, *{self.args!r})'


class Emit(MiniLinq):
    """
    This MiniLinq writes a whole table to whatever writer is registered
    in the `env`. In practice,  a table to a dict of a name, headers,
    and rows, so the writer is free to do an idempotent upsert, etc.

    Note that it does not actually check that the number of headings is
    correct, nor does it try to ensure that the things being emitted are
    actually lists - it is just crashy instead.
    """

    def __init__(
        self,
        table: str,
        headings: ListType[MiniLinq],
        source: MiniLinq,
        missing_value: Optional[str] = None,
        data_types: Optional[ListType[Literal]] = None,
    ) -> None:
        """
        Initializes an ``Emit`` instance.

        :param table: The name/title of the table to be written.
        :param headings: Evaluated to determine column headings.
        :param source: Evaluated to determine the table rows.
        :param missing_value: Denotes "no value". e.g. ``"---"``
        :param data_types: The data types of the columns. e.g.
            ``[Literal('text'), Literal('date'), ...]``
        """
        self.table = table
        self.headings = headings
        self.source = source
        self.missing_value = missing_value
        self.data_types = data_types or []

    @unwrap('cell')
    def coerce_cell_blithely(self, cell):
        if isinstance(cell, list):
            if not cell:  # jsonpath returns empty list when path is not present
                return self.missing_value
            return ','.join([self.coerce_cell(item) for item in cell])
        else:
            return cell

    def coerce_cell(self, cell):
        try:
            return self.coerce_cell_blithely(cell)
        except Exception:
            logger.exception(
                f'Error converting value to exportable form: {cell!r}'
            )
            return ''

    def coerce_row(self, row):
        return [self.coerce_cell(cell) for cell in row]

    def eval(self, env):
        rows = self.source.eval(env)
        env.emit_table(
            TableSpec(
                name=self.table,
                headings=[heading.eval(env) for heading in self.headings],
                rows=map(self.coerce_row, rows),
                data_types=[lit.v for lit in self.data_types]
            )
        )

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Emit']
        return cls(
            table=fields['table'],
            source=MiniLinq.from_jvalue(fields['source']),
            headings=[
                MiniLinq.from_jvalue(heading) for heading in fields['headings']
            ],
            missing_value=fields.get('missing_value'),
            data_types=fields.get('data_types'),
        )

    def to_jvalue(self):
        return {
            'Emit': {
                'table':
                    self.table,
                'headings': [heading.to_jvalue() for heading in self.headings],
                'source':
                    self.source.to_jvalue(),
                'missing_value':
                    self.missing_value,
                'data_types': [
                    heading.to_jvalue() for heading in self.headings
                ]
            }
        }

    def __eq__(self, other):
        return (
            isinstance(other, Emit) and self.table == other.table
            and self.headings == other.headings and self.source == other.source
            and self.missing_value == other.missing_value
            and self.data_types == other.data_types
        )

    def __repr__(self):
        return (
            f'{self.__class__.__name__}'
            f'(table={self.table!r}, '
            f'headings={self.headings!r}, '
            f'source={self.source!r}, '
            f'missing_value={self.missing_value!r})'
        )


### Register everything with the root parser ###

MiniLinq.register(Reference, slug='Ref')
MiniLinq.register(Literal, slug='Lit')
MiniLinq.register(Map)
MiniLinq.register(Filter)
MiniLinq.register(FlatMap)
MiniLinq.register(Apply)
MiniLinq.register(Emit)
MiniLinq.register(List)
MiniLinq.register(Bind)
