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
        return self.generator()

    def __bool__(self):
        try:
            next(self.__iter__())
            return True
        except StopIteration:
            return False

    __nonzero__ = __bool__

    @classmethod
    def to_jvalue(cls, obj):
        if isinstance(obj, cls):
            return list(obj)
        raise TypeError(repr(obj) + 'is not JSON serializable')
