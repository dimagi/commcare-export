# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import unittest
import hashlib
import tempfile
import struct

from commcare_export import misc
from commcare_export.map_format import parse_template


class TestDigestFile(unittest.TestCase):

    def check_digest(self, contents):
        with tempfile.NamedTemporaryFile(prefix='commcare-export-test-', mode='wb') as file:
            file.write(contents) 
            file.flush()
            file_digest = misc.digest_file(file.name)

        assert file_digest == hashlib.md5(contents).hexdigest() # Make sure the chunking does not mess with stuff
    
    def test_digest_file_ascii(self):
        self.check_digest('Hello'.encode('utf-8')) # Even a call to `write` requires encoding (as it should) in Python 3

    def test_digest_file_long(self):
        self.check_digest(('Hello' * 100000).encode('utf-8'))

    def test_digest_file_utf8(self):
        self.check_digest('Miércoles'.encode('utf-8'))

    def test_digest_file_binary(self):
        self.check_digest(struct.pack('III'.encode('ascii'), 1, 2, 3))
