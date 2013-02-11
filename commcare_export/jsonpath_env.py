
class JsonPathEnv(object):
    """
    An environment like those that map names
    to variables, but supporting dereferencing
    an JsonPath expression.
    """
    def __init__(self, bindings=None):
        self.__bindings = bindings or {}

    def lookup(self, name):
        "str|JsonPath -> ??"
        # TODO: parse the str as JsonPath using a library,
        # and just lookup via that
        if isinstance(name, basestring):
            bits = name.split('.')
            curr = self.__bindings
            for field in bits:
                if field == '@':
                    pass
                elif curr == None:
                    pass
                elif field in curr:
                    curr = curr[field]
                else:
                    curr = None
            return curr
        else:
            # TODO: JsonPath does not exist, and we need
            # to actually depend on the library
            raise NotImplementedError() 

    def bind(self, *args):
        "(str, ??) -> Env | ({str: ??}) -> Env"
        # TODO: integrate with jsonpath_rw so that
        # it is easy to write to the environment
        # as well
        
        new_bindings = dict(self.__bindings)
        if isinstance(args[0], dict):
            new_bindings.update(args[0])
            return self.__class__(new_bindings)
        
        elif isinstance(args[0], basestring):
            new_bindings[args[0]] = args[1]
            return self.__class__(new_bindings)

        else:
            raise ValueError('Bad args to Env.bind')

    def replace(self, data):
        return self.__class__(data)
