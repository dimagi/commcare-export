from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import functools
import hashlib
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


def unwrap(fn):
    @functools.wraps(fn)
    def _inner(*args):
        val = args[1] if len(args) == 2 else args[0]

        if isinstance(val, RepeatableIterator):
            val = list(val)[0]

        if isinstance(val, jsonpath.DatumInContext):
            val = val.value

        return fn(*([val] if len(args) == 1 else [args[0], val]))

    return _inner
