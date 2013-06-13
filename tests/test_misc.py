# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes
import unittest
import tempfile

from commcare_export import misc

class TestDigestFile(unittest.TestCase):
    def test_digest_file(self):
        with tempfile.NamedTemporaryFile(prefix='commcare-export-test-') as file:
            file.write('Hello'.encode('utf-8')) # Even a call to `write` requires encoding (as it should) in Python 3
            file.flush()
            misc.digest_file(file.name)
