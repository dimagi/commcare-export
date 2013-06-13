from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import hashlib
import io
import json

def digest_file(path):
    with io.open(path, encoding='utf-8') as fh:
        query_file_md5 = hashlib.md5(fh.read()).hexdigest()
