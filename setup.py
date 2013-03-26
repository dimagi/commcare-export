import os.path
import sys
import subprocess
import setuptools 

# Build README.txt from README.md if not present, and if we are actually building for distribution to pypi
if not os.path.exists('README.txt') and 'sdist' in sys.argv:
    subprocess.call(['pandoc', '--to=rst', '--smart', '--output=README.txt', 'README.md'])

readme = 'README.txt' if os.path.exists('README.txt') else 'README.md'

setuptools.setup(   
    name = "commcare-export",
    version = "0.2",
    description = 'A command-line tool (and Python library) to extract data from CommCareHQ into a SQL database or Excel workbook',
    long_description = open(readme).read(),
    author = 'Dimagi',
    author_email = 'information@dimagi.com',
    url = "https://github.com/dimagi/commcare-export",
    entry_points = { 'console_scripts': ['commcare-export = commcare_export.cli:entry_point'] },
    packages = ['commcare_export'],
    license = 'MIT',
    install_requires = ['jsonpath_rw>=0.7', 
                        'requests',
                        'simplejson',
                        'python-dateutil',
                        'argparse'],
)
