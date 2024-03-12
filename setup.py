import glob
import io
import os.path
import re
import sys

import setuptools
from setuptools.command.test import test as TestCommand

VERSION_PATH = 'commcare_export/VERSION'

# Overwrite VERSION if we are actually building for a distribution to pypi
# This code path requires dependencies, etc, to be available
if 'sdist' in sys.argv:
    import commcare_export.version
    with io.open(VERSION_PATH, 'w', encoding='ascii') as fh:
        fh.write(commcare_export.version.git_version())

# This import requires either commcare_export/VERSION or to be in a git clone (as does the package in general)
import commcare_export

version = commcare_export.version.version()

# Crash if the VERSION is not a simple version and it is going to register or upload
if 'register' in sys.argv or 'upload' in sys.argv:
    version = commcare_export.version.stored_version()
    if not version or not re.match(r'\d+\.\d+\.\d+', version):
        print('Version %s is not an appropriate version for publicizing!' %
              version)
        sys.exit(1)

readme = 'README.md'


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['-vv', '--tb=short']
        self.test_suite = True

    def run_tests(self):
        #import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(['tests/'] + self.test_args)
        sys.exit(errno)


test_deps = ['pytest', 'psycopg2', 'mock']
base_sql_deps = ["SQLAlchemy", "alembic"]
postgres = ["psycopg2"]
mysql = ["pymysql"]
odbc = ["pyodbc"]

setuptools.setup(
    name="commcare-export",
    version=version,
    description='A command-line tool (and Python library) to extract data from '
    'CommCare HQ into a SQL database or Excel workbook',
    long_description=io.open(readme, encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author='Dimagi',
    author_email='information@dimagi.com',
    url="https://github.com/dimagi/commcare-export",
    entry_points={
        'console_scripts': [
            'commcare-export = commcare_export.cli:entry_point',
            'commcare-export-utils = commcare_export.utils_cli:entry_point'
        ]
    },
    packages=setuptools.find_packages(exclude=['tests*']),
    data_files=[
        (os.path.join('share', 'commcare-export', 'examples'),
         glob.glob('examples/*.json') + glob.glob('examples/*.xlsx')),
    ],
    include_package_data=True,
    license='MIT',
    python_requires=">=3.6",
    install_requires=[
        'alembic',
        'argparse',
        'backoff>=2.0',
        'jsonpath-ng~=1.6.0',
        'ndg-httpsclient',
        'openpyxl==2.5.12',
        'python-dateutil',
        'pytz',
        'requests',
        'simplejson',
        'sqlalchemy~=1.4',
        'sqlalchemy-migrate'
    ],
    extras_require={
        'test': test_deps,
        'base_sql': base_sql_deps,
        'postgres': base_sql_deps + postgres,
        'mysql': base_sql_deps + mysql,
        'odbc': base_sql_deps + odbc,
        'xlsx': ["openpyxl"],
        'xls': ["xlwt"],
    },
    cmdclass={'test': PyTest},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Healthcare Industry',
        'Intended Audience :: Science/Research',
        'Intended Audience :: System Administrators',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Database',
        'Topic :: Software Development :: Interpreters',
        'Topic :: System :: Archiving',
        'Topic :: System :: Distributed Computing',
    ]
)
