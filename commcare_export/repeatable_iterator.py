from types import GeneratorType


class RepeatableIterator(object):
    """
    Pass something iterable into this and, 
    unless it has crufty issues, voila.
    """
    
    def __init__(self, generator):
        self.generator = generator
        self.__val = None

    def __iter__(self):
        if self.__val is None:
            self.__val = self.generator()
        return self.__val

    def __nonzero__(self):
        val = self.__iter__()
        if isinstance(val, GeneratorType):
            self.__val = list(val)
        return self.__val.__len__() > 0

    @classmethod
    def to_jvalue(cls, obj):
        if isinstance(obj, cls):
            return list(obj)
        raise TypeError(repr(obj) + 'is not JSON serializable')
