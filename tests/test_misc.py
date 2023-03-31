import hashlib
import struct
import tempfile
import unittest

from commcare_export import misc


class TestDigestFile(unittest.TestCase):

    def check_digest(self, contents):
        with tempfile.NamedTemporaryFile(
            prefix='commcare-export-test-', mode='wb'
        ) as file:
            file.write(contents)
            file.flush()
            file_digest = misc.digest_file(file.name)

        # Make sure the chunking does not mess with stuff
        assert file_digest == hashlib.md5(contents).hexdigest()

    def test_digest_file_ascii(self):
        self.check_digest('Hello'.encode('utf-8'))

    def test_digest_file_long(self):
        self.check_digest(('Hello' * 100000).encode('utf-8'))

    def test_digest_file_utf8(self):
        self.check_digest('Miércoles'.encode('utf-8'))

    def test_digest_file_binary(self):
        self.check_digest(struct.pack('III'.encode('ascii'), 1, 2, 3))
