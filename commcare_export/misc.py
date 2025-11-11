import functools
import hashlib
import inspect
import io

from commcare_export.repeatable_iterator import RepeatableIterator
from jsonpath_ng import jsonpath


def digest_file(path):
    with io.open(path, 'rb') as filehandle:
        digest = hashlib.md5()
        while True:
            # Arbitrary choice of size to be ~filesystem block size friendly
            chunk = filehandle.read(4096)
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()


def unwrap(arg_name):
    """
    A decorator that extracts the inner value of a named parameter
    ``arg_name``, and passes it to the decorated function.

    e.g.

    >>> @unwrap('val')
    ... def get_value(val):
    ...     return val
    >>> get_value([42])
    42

    """

    def unwrapper(fn):
        # Find the position of `arg_name` among the arguments of `fn`
        sig = inspect.signature(fn)
        parameters = list(sig.parameters.keys())
        position = parameters.index(arg_name)

        @functools.wraps(fn)
        def _inner(*args):
            args = list(args)
            args[position] = unwrap_val(args[position])  # Unwrap `arg_name`
            return fn(*args)

        return _inner

    return unwrapper


def unwrap_val(val):
    """
    Extracts the inner value of ``val``.

    e.g.

    >>> unwrap_val([42])
    42

    """
    if isinstance(val, RepeatableIterator):
        val = list(val)

    if isinstance(val, list):
        if len(val) == 1:
            val = val[0]
        else:
            val = [unwrap_val(v) for v in val]

    if isinstance(val, jsonpath.DatumInContext):
        val = val.value

    return val


def default_to_json(obj):
    if hasattr(obj, 'toJSON'):
        return obj.toJSON()
    else:
        return RepeatableIterator.to_jvalue(obj)
