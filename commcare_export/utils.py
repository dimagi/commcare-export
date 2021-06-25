from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import hashlib
import json
import os
import sys

from six.moves import input

from commcare_export import misc
from commcare_export.checkpoint import CheckpointManager
from commcare_export.version import __version__
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


def get_reporting_payload(args, query, writer):
    query_jval = query.to_jvalue()
    tables = []
    if os.path.splitext(args.query)[1] in ['.xls', '.xlsx']:
        from commcare_export.excel_query import parse_workbook
        parsed_sheets = parse_workbook(args.query)
        for sheet in parsed_sheets:
            root_expr = sheet.root_expr.to_jvalue() if sheet.root_expr else None
            tables.append({
                "data_source": sheet.data_source,
                "root_expression": root_expr
            })

    return {
        "version": __version__,
        "domain": args.project,
        "query": query_jval,
        "query_hash": hashlib.sha1(json.dumps(query_jval).encode("utf8")).hexdigest(),
        "writer_type": writer.name,
        "writer_subtype": writer.subtype,
        "export_tables": tables
    }


def send_reporting_payload(args, query, writer, api_client):
    """Send basic reporting data to CommCare for usage analysis"""
    payload = get_reporting_payload(args, query, writer)
    try:
        api_client.post("det_info", json=payload)
    except Exception:
        pass


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
