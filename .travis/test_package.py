import sys

from commcare_export.checkpoint import CheckpointManager

sql_url = 'postgresql://postgres@localhost/ccexport_test'

if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        sql_url = args[0]

    CheckpointManager(sql_url).create_checkpoint_table()
