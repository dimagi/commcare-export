
class MiniLinq(object):
    """
    The abstract base class for MiniLinqs, and also the factory/registry
    for dispatching parsing, etc.
    """

    def __init__(self, *args, **kwargs):
        raise NotImplementedError()

    def eval(self, env):
        "( env: object(bindings: {str: ??}, writer: Writer) )-> ??"
        raise NotImplementedError()
    
    #### Factory methods ####

    _node_classes = {}

    @classmethod
    def register(cls, clazz, slug=None):
        cls._node_classes[slug or clazz.__name__] = clazz

    @classmethod
    def from_jvalue(cls, jvalue):
        """
        The term `jvalue` is code for "the output of a JSON deserialization". This 
        module does not actually care about JSON, which is concrete syntax, but 
        only the corresponding data model of lists and string-indexed dictionaries.

        (since this data might never actually be a string, that layer is handled elsewhere)
        """

        # This is a bit wonky, but this method really should not be inherited.
        # So if we end up here from a subclass, it is broken.
        if not issubclass(MiniLinq, cls):
            raise NotImplementedError()
    
        if isinstance(jvalue, unicode):
            return jvalue

        elif isinstance(jvalue, basestring):
            return unicode(jvalue)
    
        elif isinstance(jvalue, list):
            # Leverage for literal lists of data in the code
            return [from_jvalue(v) for v in jvalue]

        elif isinstance(jvalue, dict):
            # Dictionaries are reserved; they must always have exactly
            # one entry and it must be the AST node class
            if len(jvalue.values()) != 1:
                raise ValueError('JValue serialization of AST contains dict with number of slugs != 1')
            slug = jvalue.keys()[0]

            if slug not in cls._node_classes:
                raise ValueError('JValue serialization of AST contains unknown node type: %s' % slug)

            return cls._node_classes[slug].from_jvalue(jvalue)

class Reference(MiniLinq):
    """
    An MiniLinq referencing a datum or data. It is flexible
    about what the type of the environment is, but it must
    support using these as keys
    """
    def __init__(self, ref):
        self.ref = ref
    
    def eval(self, env):
        return env.lookup(self.ref)

    def __eq__(self, other):
        return isinstance(other, Reference) and self.ref == other.ref

    @classmethod
    def from_jvalue(cls, jvalue):
        return cls(jvalue['Ref'])

    def to_jvalue(self):
        return {'Ref': self.ref}

class Literal(MiniLinq):
    """
    An MiniLinq wrapper around a python value. Returns exactly the
    value given to it. Note: when going to/from jvalue the
    contents are left alone, so it can be _used_ with a non-JSON
    encodable value, but cannot be encoded.
    """
    def __init__(self, v):
        self.v = v
    
    def eval(self, env):
        return self.v

    def __eq__(self, other):
        return isinstance(other, Literal) and self.v == other.v

    @classmethod
    def from_jvalue(cls, jvalue):
        return cls(jvalue['Lit'])

    def to_jvalue(self):
        return {'Lit': self.v}

class Alias(MiniLinq):
    """
    A way to make convenient aliases, since form types, and maybe other things,
    are just referenceable by UUID. A la `let x = 5 in x * x` but with a name
    that might make sense to a broader audience.
    """

    def __init__(self, name, value, body):
        "(str, MiniLinq, MiniLinq) -> MiniLinq"
        self.name = name
        self.value = value
        self.body = body

    def eval(self, env):
        return self.body.eval(env.bind(self.name, self.value.eval(env)))

    def __eq__(self, other):
        return isinstance(other, Alias) and self.name == other.name and self.value == other.value and self.body == other.body


class Filter(MiniLinq):
    """
    Just what it sounds like
    """

    def __init__(self, source, predicate, name=None):
        "(MiniLinq, MiniLinq, var?) -> MiniLinq"
        self.source = source
        self.name = name
        self.predicate = predicate

    def eval(self, env):
        source_result = self.source.eval(env)

        def iterate(env=env, source_result=source_result): # Python closure workaround
            if self.name:
                for item in source_result:
                    if self.predicate.eval(env.bind(name, item)):
                        yield item
            else:
                for item in source_result:
                    if self.predicate.eval(env.replace(item)):
                        yield item

        return RepeatableIterator(iterate)

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Filter']

        # TODO: catch errors and give informative error messages
        return cls(predicate   = MiniLinq.from_jvalue(fields['predicate']),
                   source = MiniLinq.from_jvalue(fields['source']),
                   name   = fields.get('name'))

    def to_jvalue(self):
        return {'Filter': {'predicate': self.predicate,
                           'source': self.source,
                           'name': self.name}}

class Map(MiniLinq):
    """
    Like the `FROM` clause of a SQL `SELECT` or jQuery's map,
    binds each item from its `source` and evaluates
    the body MiniLinq.

    If `name` is provided to the constructor, then instead of
    replacing the environment with each row, it will just
    bind the row to `name`, enabling references to the
    rest of the env.
    """

    def __init__(self, source, body, name=None):
        "(MiniLinq, MiniLinq, var?) -> MiniLinq"
        self.source = source
        self.name = name
        self.body = body
    
    def eval(self, env):
        source_result = self.source.eval(env)

        def iterate(env=env, source_result=source_result): # Python closure workaround
            if self.name:
                for item in source_result:
                    yield self.body.eval(env.bind(name, item))
            else:
                for item in source_result:
                    yield self.body.eval(env.replace(item)) 

        return RepeatableIterator(iterate)

    def __eq__(self, other):
        return isinstance(other, Map) and self.name == other.name and self.source == other.source and self.body == other.body

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Map']

        # TODO: catch errors and give informative error messages
        return cls(body   = MiniLinq.from_jvalue(fields['body']),
                   source = MiniLinq.from_jvalue(fields['source']),
                   name   = fields.get('name'))

    def to_jvalue(self):
        return {'Map': {'body': self.body,
                        'source': self.source,
                        'name': self.name}}
class FlatMap(MiniLinq):
    """
    Somewhat like a JOIN, but not quite. Called `SelectMany`
    in LINQ and `flatMap` other languages. Obvious equivalence:
    `flatMap f = flatten . map f` but so common it is useful to
    have around.

    If `name` is provided to the constructor, then instead of
    replacing the environment with each row, it will just
    bind the row to `name`, enabling references to the
    rest of the env.
    """

    def __init__(self, source, body, name=None):
        "(MiniLinq, MiniLinq, var?) -> MiniLinq"
        self.source = source
        self.name = name
        self.body = body
    
    def eval(self, env):
        source_result = self.source.eval(env)

        def iterate(env=env, source_result=source_result): # Python closure workaround
            if self.name:
                for item in source_result:
                    for result_item in self.body.eval(env.bind(name, item)):
                        yield result_item
            else:
                for item in source_result:
                    for result_item in self.body.eval(env.replace(item)):
                        yield result_item

        return RepeatableIterator(iterate)

    def __eq__(self, other):
        return isinstance(other, FlatMap) and self.name == other.name and self.source == other.source and self.body == other.body


    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['FlatMap']

        # TODO: catch errors and give informative error messages
        return cls(body   = MiniLinq.from_jvalue(fields['body']),
                   source = MiniLinq.from_jvalue(fields['source']),
                   name   = fields.get('name'))

    def to_jvalue(self):
        return {'FlatMap': {'body': self.body,
                            'source': self.source,
                            'name': self.name}}

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

        return fn_result(*args_results)

    def __eq__(self, other):
        return isinstance(other, Apply) and self.fn == other.fn and self.args == other.args

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Apply']

        # TODO: catch errors and give informative error messages
        return cls(MiniLinq.from_jvalue(fields['fn']),
                   *[MiniLinq.from_jvalue(arg) for arg in fields['args']])

    def to_jvalue(self):
        return {'Apply': {'fn': self.fn.to_jvalue(),
                          'args': [arg.to_jvalue() for arg in self.args]}}

class Emit(MiniLinq):
    """
    This MiniLinq has only the side effect of writing a collection
    of results to a new table (via whatever writer is present in the environment)
    """
    def __init__(self, table_name, body):
        self.table_name = table_name
        self.body = body

    def eval(self, env):
        body_results = self.body.eval(env)
        env.writer.write_table(table_name, body_results)

    @classmethod
    def from_jvalue(cls, jvalue):
        fields = jvalue['Emit']

        # TODO: catch errors and give informative error messages
        return cls(table_name = fields['table_name'],
                   body       = MiniLinq.from_jvalue(fields['body']))

    def to_jvalue(self):
        return {'Emit': {'table_name': self.table_name,
                         'body': self.body.to_jvalue()}}

class Columns(MiniLinq):
    def __init__(self, columns):
        """
        ([(str, MiniLinq)] -> MiniLinq

        Each item in the `columns` list gives a header
        for the column and the expression to populate
        the column with.
        """
        self.columns = columns

    def eval(self, env):
        return dict([ (field, expr.eval(env)) for field, expr in self.columns.items() ])

### Utility class

class RepeatableIterator(object):
    def __init__(self, generator):
        self.generator = generator

    def __iter__(self):
        return self.generator()
    
### Register everything with the root parser ###

MiniLinq.register(Reference, slug='Ref')
MiniLinq.register(Literal, slug='Lit')
MiniLinq.register(Map)
MiniLinq.register(Filter)
MiniLinq.register(FlatMap)
MiniLinq.register(Apply)
MiniLinq.register(Emit)
