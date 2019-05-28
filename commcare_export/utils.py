from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import sys

from commcare_export import misc
from commcare_export.checkpoint import CheckpointManager
from six.moves import input

from commcare_export.writers import StreamingMarkdownTableWriter


def get_checkpoint_manager(args, require_query=True):
    md5 = None
    try:
        md5 = misc.digest_file(args.query)
    except Exception:
        if require_query:
            raise

    return CheckpointManager(
        args.output, args.query, md5,
        args.project, args.commcare_hq, args.checkpoint_key
    )


def confirm(message):
    confirm = input(
        """
        {}? [y/N]
        """.format(message)
    )
    return confirm == "y"


def print_runs(runs):
    print()
    rows = []
    for run in runs:
        rows.append([
            run.time_of_run, run.since_param, "True" if run.final else "False",
            run.project, run.query_file_name, run.query_file_md5, run.key, run.table_name, run.commcare
        ])

    rows = [
        [val if val is not None else '' for val in row]
        for row in rows
    ]

    StreamingMarkdownTableWriter(sys.stdout, compute_widths=True).write_table({
        'headings': [
            "Checkpoint Time", "Batch end date", "Export Complete",
            "Project", "Query Filename", "Query MD5", "Key", "Table", "CommCare HQ"
        ],
        'rows': rows
    })
