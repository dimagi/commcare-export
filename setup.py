import os.path
import sys
import glob
import io
import subprocess
import setuptools 
from setuptools.command.test import test as TestCommand

# Build README.txt from README.md if not present, and if we are actually building for distribution to pypi
if not os.path.exists('README.txt') and 'sdist' in sys.argv:
    subprocess.call(['pandoc', '--to=rst', '--output=README.txt', 'README.md'])

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
    version = "0.10.5",
    description = 'A command-line tool (and Python library) to extract data from CommCareHQ into a SQL database or Excel workbook',
    long_description = io.open(readme, encoding='utf-8').read(),
    author = 'Dimagi',
    author_email = 'information@dimagi.com',
    url = "https://github.com/dimagi/commcare-export",
    entry_points = { 'console_scripts': ['commcare-export = commcare_export.cli:entry_point'] },
    packages = ['commcare_export'],
    data_files = [(os.path.join('share', 'commcare-export', 'examples'), glob.glob('examples/*.json') + glob.glob('examples/*.xlsx'))],
    license = 'MIT',
    install_requires = ['jsonpath-rw>=1.1',
                        'openpyxl',
                        'six',
                        'openpyxl',
                        'requests',
                        'simplejson',
                        'python-dateutil',
                        'sqlalchemy',
                        'alembic',
                        'argparse'],
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
