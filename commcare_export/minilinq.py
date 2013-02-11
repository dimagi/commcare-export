
class Env(object):
    def bind(self, *args):
        "(key, ??) -> Env | ({key: ??}) -> Env"
        raise NotImplementedError()

    def lookup(self, key):
        """
        key -> ??

        Note that the ?? may be None which may mean
        the value was unbound or may mean it was
        found and was None. This may need revisiting.
        """
        raise NotImplementedError()

    def replace(self, data):
        """
        data -> Env

        Completely replace the environment with new
        data (somewhat like "this"-based Map functions a la jQuery).
        Could be the same as creating a new empty env
        and binding "@" in JsonPath.
        """
        raise NotImplementedError()

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

    @classmethod
    def from_jvalue(cls, jvalue):
        return cls(jvalue['Ref'])

    def to_jvalue(self):
        return {'Ref': self.ref}

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

class RepeatableIterator(object):
    def __init__(self, generator):
        self.generator = generator

    def __iter__(self):
        return self.generator()

class EmitMiniLinq(MiniLinq):
    """
    This MiniLinq has only the side effect of writing a collection
    of results to a new table (via whatever writer is present in the environment)
    """
    pass

class Columns(MiniLinq):
    def __init__(self, columns):
        "({str: MiniLinq} -> MiniLinq"
        self.columns = columns

    def eval(self, env):
        return dict([ (field, expr.eval(env)) for field, expr in self.columns.items() ])

    
### Register everything with the root parser ###

MiniLinq.register(Reference, slug='Ref')
MiniLinq.register(Map)
MiniLinq.register(Filter)

