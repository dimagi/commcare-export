from __future__ import print_function
import os.path
import sys
import glob
import re
import io
import subprocess
import setuptools 
from setuptools.command.test import test as TestCommand

VERSION_PATH='commcare_export/VERSION'

# Build README.txt from README.md if not present, and if we are actually building for distribution to pypi
if not os.path.exists('README.txt') and 'sdist' in sys.argv:
    subprocess.call(['pandoc', '--to=rst', '--output=README.txt', 'README.md', '--columns=160'])

# Overwrite VERSION if we are actually building for a distribution to pypi
# This code path requires dependencies, etc, to be available
if 'sdist' in sys.argv:
    import commcare_export.version
    with io.open(VERSION_PATH, 'w', encoding='ascii') as fh:
        fh.write(commcare_export.version.git_version())

# This import requires either commcare_export/VERSION or to be in a git clone (as does the package in general)
import commcare_export
version = commcare_export.__version__

# Crash if the VERSION is not a simple version and it is going to register or upload
if 'register' in sys.argv or 'upload' in sys.argv:
    if not re.match('\d+\.\d+\.\d+', version):
        print('Version %s is not an appropriate version for publicizing!' % version)
        sys.exit(1)

readme = 'README.txt' if os.path.exists('README.txt') else 'README.md'

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(['tests/'] + self.test_args)
        sys.exit(errno)

setuptools.setup(   
    name = "commcare-export",
    version = version,
    description = 'A command-line tool (and Python library) to extract data from CommCareHQ into a SQL database or Excel workbook',
    long_description = io.open(readme, encoding='utf-8').read(),
    author = 'Dimagi',
    author_email = 'information@dimagi.com',
    url = "https://github.com/dimagi/commcare-export",
    entry_points = { 'console_scripts': ['commcare-export = commcare_export.cli:entry_point'] },
    packages = ['commcare_export'],
    data_files = [(os.path.join('share', 'commcare-export', 'examples'), glob.glob('examples/*.json') + glob.glob('examples/*.xlsx'))],
    package_data = {'': ['VERSION']},
    license = 'MIT',
    install_requires = [
        'alembic',
        'argparse',
        'jsonpath-rw>=1.2.1',
        'openpyxl<2.1.0',
        'python-dateutil',
        'requests',
        'ndg-httpsclient',
        'simplejson',
        'six',
        'sqlalchemy',
        'pytz'
    ],
    tests_require = ['pytest', 'psycopg2'],
    cmdclass = {'test': PyTest},
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Healthcare Industry',
        'Intended Audience :: Science/Research',
        'Intended Audience :: System Administrators',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Topic :: Database',
        'Topic :: Software Development :: Interpreters',
        'Topic :: System :: Archiving',
        'Topic :: System :: Distributed Computing',
    ],
)
