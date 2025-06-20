import argparse
import getpass
import io
import json
import os.path
import sys
import logging
import dateutil.parser
import requests
import sqlalchemy

from commcare_export import builtin_queries, excel_query, writers
from commcare_export.checkpoint import CheckpointManagerProvider
from commcare_export.commcare_hq_client import (
    LATEST_KNOWN_VERSION,
    CommCareHqClient,
    ResourceRepeatException,
)
from commcare_export.commcare_minilinq import CommCareHqEnv
from commcare_export.env import BuiltInEnv, EmitterEnv, JsonPathEnv
from commcare_export.exceptions import (
    DataExportException,
    MissingQueryFileException,
)
from commcare_export.location_info_provider import LocationInfoProvider
from commcare_export.minilinq import List, MiniLinq
from commcare_export.misc import default_to_json
from commcare_export.repeatable_iterator import RepeatableIterator
from commcare_export.utils import get_checkpoint_manager
from commcare_export.version import __version__
from commcare_export import get_logger, get_error_logger

EXIT_STATUS_ERROR = 1
logger = get_logger(__file__)

commcare_hq_aliases = {
    'local': 'http://localhost:8000',
    'prod': 'https://www.commcarehq.org'
}


class Argument:

    def __init__(self, name, *args, **kwargs):
        self.name = name.replace('-', '_')
        self._args = [f'--{name}'] + list(args)
        self._kwargs = kwargs

    @property
    def default(self):
        return self._kwargs.get('default')

    def add_to_parser(self, parser, **additional_kwargs):
        additional_kwargs.update(self._kwargs)
        parser.add_argument(*self._args, **additional_kwargs)


CLI_ARGS = [
    Argument(
        'version',
        default=False,
        action='store_true',
        help='Print the current version of the commcare-export tool.'
    ),
    Argument('query', required=False, help='JSON or Excel query file'),
    Argument('dump-query', default=False, action='store_true'),
    Argument(
        'commcare-hq',
        default='prod',
        help='Base url for the CommCare HQ instance e.g. '
        'https://www.commcarehq.org'
    ),
    Argument('api-version', default=LATEST_KNOWN_VERSION),
    Argument('project'),
    Argument('username'),
    Argument(
        'password',
        help='Enter password, or if using apikey auth-mode, enter the api key.'
    ),
    Argument(
        'auth-mode',
        default='password',
        choices=['password', 'apikey'],
        help='Use "digest" auth, or "apikey" auth (for two factor enabled '
        'domains).'
    ),
    Argument(
        'since',
        help='Export all data after this date. Format YYYY-MM-DD or '
        'YYYY-MM-DDTHH:mm:SS'
    ),
    Argument(
        'until',
        help='Export all data up until this date. Format YYYY-MM-DD or '
        'YYYY-MM-DDTHH:mm:SS'
    ),
    Argument(
        'start-over',
        default=False,
        action='store_true',
        help='When saving to a SQL database; the default is to pick up '
        'since the last success. This disables that.'
    ),
    Argument('verbose', default=False, action='store_true'),
    Argument(
        'output-format',
        default='json',
        choices=['json', 'csv', 'xls', 'xlsx', 'sql', 'markdown'],
        help='Output format'
    ),
    Argument(
        'output',
        metavar='PATH',
        default='reports.zip',
        help='Path to output; defaults to `reports.zip`.'
    ),
    Argument(
        'strict-types',
        default=False,
        action='store_true',
        help="When saving to a SQL database don't allow changing column types "
        "once they are created."
    ),
    Argument(
        'missing-value',
        default=None,
        help="Value to use when a field is missing from the form / case."
    ),
    Argument(
        'batch-size',
        default=200,
        help="Number of records to process per batch."
    ),
    Argument(
        'checkpoint-key',
        help="Use this key for all checkpoints instead of the query file MD5 "
        "hash in order to prevent table rebuilds after a query file has "
        "been edited."
    ),
    Argument(
        'users',
        default=False,
        action='store_true',
        help="Export a table containing data about this project's mobile "
        "workers"
    ),
    Argument(
        'locations',
        default=False,
        action='store_true',
        help="Export a table containing data about this project's locations"
    ),
    Argument(
        'with-organization',
        default=False,
        action='store_true',
        help="Export tables containing mobile worker data and location data "
        "and add a commcare_userid field to any exported form or case"
    ),
    Argument(
        'export-root-if-no-subdocument',
        default=False,
        action='store_true',
        help="Use this when you are exporting a nested document e.g. "
        "form.form..case, messaging-event.messages.[*] And you want to "
        "have a record exported even if the nested document does not "
        "exist or is empty.",
    ),
    Argument(
        'no-logfile',
        default=False,
        help="Specify in order to prevent information being logged to the log file and"
             " show all output in the console.",
        action='store_true',
    ),
]


def main(argv):
    parser = argparse.ArgumentParser(
        'commcare-export', 'Output a customized export of CommCareHQ data.'
    )
    for arg in CLI_ARGS:
        arg.add_to_parser(parser)

    args = parser.parse_args(argv)

    if args.output_format and args.output:
        errors = []
        errors.extend(validate_output_filename(args.output_format, args.output))
        if errors:
            raise Exception(f"Could not proceed. Following issues were found: {', '.join(errors)}.")

    if not args.no_logfile:
        exe_dir = os.path.dirname(sys.executable)
        log_file = os.path.join(exe_dir, "commcare_export.log")
        print(f"Printing logs to {log_file}")
        logging.basicConfig(
            filename=log_file,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
            filemode='w',
        )
        sys.stderr = get_error_logger()

    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
        )
    else:
        logging.basicConfig(
            level=logging.WARN,
            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
        )

    logging.getLogger('alembic').setLevel(logging.WARN)
    logging.getLogger('backoff').setLevel(logging.FATAL)
    logging.getLogger('urllib3').setLevel(logging.WARN)

    if args.version:
        print(f'commcare-export version {__version__}')
        sys.exit(0)

    if not args.project:
        error_msg = "commcare-export: error: argument --project is required"
        # output to log file through sys.stderr
        print(
            error_msg,
            file=sys.stderr
        )
        # Output to console for debugging
        print(error_msg)
        sys.exit(1)

    print("Running export...")
    try:
        exit_code = main_with_args(args)
        if exit_code > 0:
            print("Error occurred! See log file for error.")
        sys.exit(exit_code)
    except Exception:
        print("Error occurred! See log file for error.")
        raise
    finally:
        print("Export finished!")


def validate_output_filename(output_format, output_filename):
    """
    Validate file extensions for csv, xls and xlsx output formats.
    Ensure extension unless using sql output_format.
    """
    errors = []
    if output_format == 'csv' and not output_filename.endswith('.zip'):
        errors.append("For output format as csv, output file name should have extension zip")
    elif output_format == 'xls' and not output_filename.endswith('.xls'):
        errors.append("For output format as xls, output file name should have extension xls")
    elif output_format == 'xlsx' and not output_filename.endswith('.xlsx'):
        errors.append("For output format as xlsx, output file name should have extension xlsx")
    elif output_format != 'sql' and "." not in output_filename:
        errors.append("Missing extension in output file name")
    return errors


def _get_query(args, writer, column_enforcer=None):
    return _get_query_from_file(
        args.query,
        args.missing_value,
        writer.supports_multi_table_write,
        writer.max_column_length,
        writer.required_columns,
        column_enforcer,
        args.export_root_if_no_subdocument
    )


def _get_query_from_file(
    query_arg,
    missing_value,
    combine_emits,
    max_column_length,
    required_columns,
    column_enforcer,
    value_or_root
):
    if os.path.exists(query_arg):
        if os.path.splitext(query_arg)[1] in ['.xls', '.xlsx']:
            import openpyxl
            workbook = openpyxl.load_workbook(query_arg)
            return excel_query.get_queries_from_excel(
                workbook,
                missing_value,
                combine_emits,
                max_column_length,
                required_columns,
                column_enforcer,
                value_or_root
            )
        else:
            with io.open(query_arg, encoding='utf-8') as fh:
                return MiniLinq.from_jvalue(json.loads(fh.read()))


def get_queries(args, writer, lp, column_enforcer=None):
    query_list = []
    if args.query is not None:
        query = _get_query(args, writer, column_enforcer=column_enforcer)

        if not query:
            raise MissingQueryFileException(args.query)
        query_list.append(query)

    if args.users or args.with_organization:
        # Add user data to query
        query_list.append(builtin_queries.users_query)

    if args.locations or args.with_organization:
        # Add location data to query
        query_list.append(builtin_queries.get_locations_query(lp))

    return List(query_list) if len(query_list) > 1 else query_list[0]


def _get_writer(output_format, output, strict_types):
    if output_format == 'xlsx':
        return writers.Excel2007TableWriter(output)
    elif output_format == 'xls':
        return writers.Excel2003TableWriter(output)
    elif output_format == 'csv':
        if not output.endswith(".zip"):
            print(
                "WARNING: csv output is a zip file, but "
                f"will be written to {output}"
            )
            print(
                "Consider appending .zip to the file name to avoid confusion."
            )
        return writers.CsvTableWriter(output)
    elif output_format == 'json':
        return writers.JValueTableWriter()
    elif output_format == 'markdown':
        return writers.StreamingMarkdownTableWriter(sys.stdout)
    elif output_format == 'sql':
        # Output should be a connection URL. Writer had bizarre issues
        # so we use a full connection instead of passing in a URL or
        # engine.
        if output.startswith('mysql'):
            charset_split = output.split('charset=')
            if len(charset_split) > 1 and charset_split[1] != 'utf8mb4':
                raise Exception(
                    f"The charset '{charset_split[1]}' might cause problems with the export. "
                    f"It is recommended that you use 'utf8mb4' instead."
                )

        return writers.SqlTableWriter(output, strict_types)
    else:
        raise Exception(f"Unknown output format: {output_format}")


def get_date_params(args):
    since = dateutil.parser.parse(args.since) if args.since else None
    until = dateutil.parser.parse(args.until) if args.until else None
    return since, until


def _get_api_client(args, commcarehq_base_url):
    return CommCareHqClient(
        url=commcarehq_base_url,
        project=args.project,
        username=args.username,
        password=args.password,
        auth_mode=args.auth_mode,
        version=args.api_version
    )


def _get_checkpoint_manager(args):
    if not args.users and not args.locations and not os.path.exists(
        args.query
    ):
        logger.warning(
            "Checkpointing disabled for non builtin, "
            "non file-based query"
        )
    elif args.since or args.until:
        logger.warning(
            "Checkpointing disabled when using '--since' or '--until'"
        )
    else:
        checkpoint_manager = get_checkpoint_manager(args)
        checkpoint_manager.create_checkpoint_table()
        return checkpoint_manager


def force_lazy_result(lazy_result):
    if lazy_result is not None:
        if isinstance(lazy_result, RepeatableIterator):
            list(lazy_result) if lazy_result else lazy_result
        else:
            for nested_result in lazy_result:
                force_lazy_result(nested_result)


def evaluate_query(env, query):
    with env:
        try:
            lazy_result = query.eval(env)
            force_lazy_result(lazy_result)
            return 0
        except requests.exceptions.RequestException as e:
            if e.response and e.response.status_code == 401:
                print(
                    "\nAuthentication failed. Please check your credentials.",
                    file=sys.stderr
                )
                return EXIT_STATUS_ERROR
            else:
                raise
        except ResourceRepeatException as e:
            print('Stopping because the export is stuck')
            print(e.message)
            print('Try increasing --batch-size to overcome the error')
            return EXIT_STATUS_ERROR
        except (
            sqlalchemy.exc.DataError,
            sqlalchemy.exc.InternalError,
            sqlalchemy.exc.ProgrammingError
        ) as e:
            print('Stopping because of database error:\n', e)
            return EXIT_STATUS_ERROR
        except KeyboardInterrupt:
            print('\nExport aborted', file=sys.stderr)
            return EXIT_STATUS_ERROR


def main_with_args(args):
    logger.info(f"CommCare Export Version {__version__}")
    writer = _get_writer(args.output_format, args.output, args.strict_types)

    if args.query is None and args.users is False and args.locations is False:
        print(
            'At least one the following arguments is required: '
            '--query, --users, --locations',
            file=sys.stderr
        )
        return EXIT_STATUS_ERROR

    if not args.username:
        logger.warn("Username not provided")
        args.username = input('Please provide a username: ')

    if not args.password:
        logger.warn("Password not provided")
        # Windows getpass does not accept unicode
        args.password = getpass.getpass()

    column_enforcer = None
    if args.with_organization:
        column_enforcer = builtin_queries.ColumnEnforcer()

    commcarehq_base_url = commcare_hq_aliases.get(
        args.commcare_hq, args.commcare_hq
    )
    api_client = _get_api_client(args, commcarehq_base_url)
    lp = LocationInfoProvider(api_client, page_size=args.batch_size)
    try:
        query = get_queries(args, writer, lp, column_enforcer)
    except DataExportException as e:
        print(e.message, file=sys.stderr)
        return EXIT_STATUS_ERROR

    if args.dump_query:
        print(json.dumps(query.to_jvalue(), indent=4))
        return

    checkpoint_manager = None
    if writer.support_checkpoints:
        checkpoint_manager = _get_checkpoint_manager(args)

    since, until = get_date_params(args)
    if args.start_over:
        if checkpoint_manager:
            logger.warning(
                'Ignoring all checkpoints and re-fetching all data from '
                'CommCare.'
            )
    elif since:
        logger.debug('Starting from %s', args.since)

    cm = CheckpointManagerProvider(checkpoint_manager, since, args.start_over)
    static_env = {
        'commcarehq_base_url': commcarehq_base_url,
        'get_checkpoint_manager': cm.get_checkpoint_manager,
        'get_location_info': lp.get_location_info,
        'get_location_ancestor': lp.get_location_ancestor
    }
    env = (
        BuiltInEnv(static_env)
        | CommCareHqEnv(api_client, until=until, page_size=args.batch_size)
        | JsonPathEnv({})
        | EmitterEnv(writer)
    )

    exit_status = evaluate_query(env, query)

    if args.output_format == 'json':
        print(
            json.dumps(
                list(writer.tables.values()),
                indent=4,
                default=default_to_json
            )
        )

    return exit_status


def entry_point():
    main(sys.argv[1:])


if __name__ == '__main__':
    entry_point()
