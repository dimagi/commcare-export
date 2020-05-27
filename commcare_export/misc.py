from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import functools
import hashlib
import inspect
import io
from jsonpath_rw import jsonpath
from commcare_export.repeatable_iterator import RepeatableIterator


def digest_file(path):
    with io.open(path, 'rb') as filehandle:
        digest = hashlib.md5()
        while True:
            chunk = filehandle.read(4096) # Arbitrary choice of size to be ~filesystem block size friendly
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()


def unwrap(arg_name):

    def unwrapper(fn):
        @functools.wraps(fn)
        def _inner(*args):
            callargs = inspect.getcallargs(fn, *args)
            val = callargs[arg_name]
            callargs[arg_name] = unwrap_val(val)
            return fn(**callargs)

        return _inner

    return unwrapper


def unwrap_val(val):
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
