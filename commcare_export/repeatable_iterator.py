
class RepeatableIterator(object):
    """
    Pass something iterable into this and, 
    unless it has crufty issues, voila.
    """
    
    def __init__(self, generator):
        self.generator = generator

    def __iter__(self):
        return self.generator()

    @classmethod
    def to_jvalue(cls, obj):
        if isinstance(obj, cls):
            return list(obj)
        raise TypeError(repr(o) + 'is not JSON serializable')
