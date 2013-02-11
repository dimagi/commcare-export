import setuptools 

setuptools.setup(   
    name = "commcare-export",
    version = "0.1",
    url = "https://github.com/dimagi/commcare-export",
    maintainer = "CommCareHQ Team",
    maintainer_email = "information@dimagi.com",
    entry_points = { 'console_scripts': ['commcare-export = commcare_export.cli:main'] },
    packages = setuptools.find_packages(),
    install_requires = ['jsonpath_rw', 
                        'requests',
                        'argparse'],
)
