from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import hashlib
import io
import json

def digest_file(path):
    with io.open(path, 'rb') as filehandle:
        digest = hashlib.md5()
        while True:
            chunk = filehandle.read(4096) # Arbitrary choice of size to be ~filesystem block size friendly
            if not chunk:
                break
            digest.update(chunk)
        return digest.hexdigest()
