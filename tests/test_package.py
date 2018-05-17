"""
This isn't a unit test. We call this after installing the tool
from the source distribution to make sure that the packaging
is working correctly.
"""
import sys

from commcare_export.checkpoint import CheckpointManager
from commcare_export import version

sql_url = 'postgresql://postgres@localhost/ccexport_test'

if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        sql_url = args[0]

    print("Test VERSION file is created and included in the package")
    assert version.stored_version()

    print("Test that migrations are included and can be found by alembic")
    CheckpointManager(sql_url).create_checkpoint_table()
