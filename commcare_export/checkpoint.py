from __future__ import unicode_literals, print_function, absolute_import, division, generators, nested_scopes

import datetime
import logging
import uuid

import os
from contextlib import contextmanager
from operator import attrgetter

import dateutil.parser
import six
from sqlalchemy import Column, String, Boolean, func, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from commcare_export.exceptions import DataExportException
from commcare_export.writers import SqlMixin

logger = logging.getLogger(__name__)
repo_root = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))

Base = declarative_base()


class Checkpoint(Base):
    __tablename__ = 'commcare_export_runs'

    id = Column(String, primary_key=True)
    query_file_name = Column(String)
    query_file_md5 = Column(String)
    table_name = Column(String)
    key = Column(String)
    project = Column(String)
    commcare = Column(String)
    since_param = Column(String)
    time_of_run = Column(String)
    final = Column(Boolean)

    def __repr__(self):
        return (
            "<Checkpoint("
            "id={r.id}, "
            "query_file_name={r.query_file_name}, "
            "query_file_md5={r.query_file_md5}, "
            "table_name={r.table_name}, "
            "key={r.key}, "
            "project={r.project}, "
            "commcare={r.commcare}, "
            "since_param={r.since_param}, "
            "time_of_run={r.time_of_run}, "
            "final={r.final})>".format(r=self)
        )


@contextmanager
def session_scope(Session):
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


class CheckpointManager(SqlMixin):
    table_name = 'commcare_export_runs'
    migrations_repository = os.path.join(repo_root, 'migrations')

    def __init__(self, db_url, query, query_md5, project, commcare, key=None, table_names=None, poolclass=None, engine=None):
        super(CheckpointManager, self).__init__(db_url, poolclass=poolclass, engine=engine)
        self.query = query
        self.query_md5 = query_md5
        self.project = project
        self.commcare = commcare
        self.key = key
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        self.table_names = table_names

    def for_tables(self, table_names):
        return CheckpointManager(
            self.db_url, self.query, self.query_md5, self.project, self.commcare, self.key,
            engine=self.engine, table_names=table_names
        )

    def set_checkpoint(self, checkpoint_time, is_final=False):
        self._set_checkpoint(checkpoint_time, is_final)
        if is_final:
            self._cleanup()

    def _set_checkpoint(self, checkpoint_time, final, time_of_run=None):
        logger.info(
            'Setting %s checkpoint for tables %s: %s',
            'final' if final else 'batch',
            ', '.join(self.table_names),
            checkpoint_time
        )
        if not checkpoint_time:
            raise DataExportException('Tried to set an empty checkpoint. This is not allowed.')
        self._validate_tables()

        if isinstance(checkpoint_time, six.text_type):
            since_param = checkpoint_time
        else:
            since_param = checkpoint_time.isoformat()

        created = []
        with session_scope(self.Session) as session:
            for table in self.table_names:
                checkpoint = Checkpoint(
                    id=uuid.uuid4().hex,
                    query_file_name=self.query,
                    query_file_md5=self.query_md5,
                    table_name=table,
                    key=self.key,
                    project=self.project,
                    commcare=self.commcare,
                    since_param=since_param,
                    time_of_run=time_of_run or datetime.datetime.utcnow().isoformat(),
                    final=final
                )
                session.add(checkpoint)
                created.append(checkpoint)
        return created

    def create_checkpoint_table(self, revision='head'):
        from alembic import command, config
        cfg = config.Config(os.path.join(self.migrations_repository, 'alembic.ini'))
        cfg.set_main_option('script_location', self.migrations_repository)
        with self.engine.begin() as connection:
            cfg.attributes['connection'] = connection
            command.upgrade(cfg, revision)

    def _cleanup(self):
        self._validate_tables()
        with session_scope(self.Session) as session:
            session.query(Checkpoint).filter_by(
                final=False, query_file_md5=self.query_md5,
                project=self.project, commcare=self.commcare
            ).filter(Checkpoint.table_name.in_(self.table_names)).delete(synchronize_session='fetch')

    def get_time_of_last_checkpoint(self, log_warnings=True):
        """Return the earliest time from the list of checkpoints that for the current
        query file / key."""
        run = self.get_last_checkpoint()
        if run and log_warnings:
            self.log_warnings(run)
        return run.since_param if run else None

    def get_last_checkpoint(self):
        """Return a single checkpoint such that it has the earliest `since_param` of all
        checkpoints for the active tables."""
        self._validate_tables()
        table_runs = []
        with session_scope(self.Session) as session:
            for table in self.table_names:
                if self.key:
                    table_run = self._get_last_checkpoint(
                        session, table_name=table,
                        key=self.key, project=self.project, commcare=self.commcare
                    )
                else:
                    table_run = self._get_last_checkpoint(
                        session, table_name=table,
                        query_file_md5=self.query_md5, project=self.project, commcare=self.commcare, key=self.key
                    )
                if table_run:
                   table_runs.append(table_run)

        if not table_runs:
            table_runs = self.get_legacy_checkpoints()

        if table_runs:
            sorted_runs = list(sorted(table_runs, key=attrgetter('time_of_run')))
            return sorted_runs[0]

    def get_legacy_checkpoints(self):
        with session_scope(self.Session) as session:
            # check without table_name
            table_run = self._get_last_checkpoint(
                session, query_file_md5=self.query_md5, table_name=None,
                project=self.project, commcare=self.commcare, key=self.key
            )
            if table_run:
                return self._set_checkpoint(table_run.since_param, table_run.final, table_run.time_of_run)

            # Check for run without the args
            table_run = self._get_last_checkpoint(
                session, query_file_md5=self.query_md5, key=self.key,
                project=None, commcare=None, table_name=None
            )
            if table_run:
                return self._set_checkpoint(table_run.since_param, table_run.final, table_run.time_of_run)

    def _get_last_checkpoint(self, session, **kwarg_filters):
        query = session.query(Checkpoint)
        if kwarg_filters:
            query = query.filter_by(**kwarg_filters)
        return query.order_by(Checkpoint.time_of_run.desc()).first()

    def log_warnings(self, run):
        # type: (Checkpoint) -> None
        md5_mismatch = run.query_file_md5 != self.query_md5
        name_mismatch = run.query_file_name != self.query
        if md5_mismatch or name_mismatch:
            logger.warning(
                "Query differs from most recent checkpoint:\n"
                "From checkpoint:         name=%s, md5=%s\n"
                "From command line args:  name=%s, md5=%s\n",
                run.query_file_name, run.query_file_md5,
                self.query, self.query_md5
            )

    def list_checkpoints(self, limit=20):
        """List all checkpoints filtered by:
        * file name
        * project
        * commcare
        * key

        Don't filter by MD5 on purpose.
        """
        with session_scope(self.Session) as session:
            query = self._filter_query(session.query(Checkpoint))
            if self.query:
                query = query.filter(Checkpoint.query_file_name == self.query)
            return query.order_by(Checkpoint.time_of_run.desc())[:limit]

    def _filter_query(self, query):
        if self.project:
            query = query.filter(Checkpoint.project == self.project)
        if self.commcare:
            query = query.filter(Checkpoint.commcare == self.commcare)
        if self.key:
            query = query.filter(Checkpoint.key == self.key)
        return query

    def get_latest_checkpoints(self):
        """Returns the latest checkpoint for each table filtered by the fields set in the manager:
        * query_md5
        * project
        * commcare
        * key
        """
        with session_scope(self.Session) as session:
            cols = [Checkpoint.project, Checkpoint.commcare, Checkpoint.query_file_md5, Checkpoint.table_name]
            inner_query = self._filter_query(
                session.query(
                    *(cols  + [func.max(Checkpoint.time_of_run).label('max_time_of_run')])
                )
                .filter(Checkpoint.query_file_md5 == self.query_md5)
                .filter(Checkpoint.table_name.isnot(None))
            ).group_by(*cols).subquery()

            query = session.query(Checkpoint).join(
                inner_query, and_(
                    Checkpoint.project == inner_query.c.project,
                    Checkpoint.commcare == inner_query.c.commcare,
                    Checkpoint.query_file_md5 == inner_query.c.query_file_md5,
                    Checkpoint.table_name == inner_query.c.table_name,
                    Checkpoint.time_of_run == inner_query.c.max_time_of_run
                )
            ).order_by(Checkpoint.table_name.asc())

            # Can't use this since MySQL < 8.0 doesn't support window functions
            # Keeping for future reference
            #
            # window_func = func.row_number().over(
            #     partition_by=Checkpoint.table_name, order_by=Checkpoint.time_of_run.desc()
            # ).label("row_number")
            # inner_query = self._filter_query(session.query(Checkpoint, window_func))
            # inner_query = inner_query.filter(Checkpoint.query_file_md5 == self.query_md5)
            # inner_query = inner_query.filter(Checkpoint.table_name.isnot(None)).subquery()
            #
            # query = session.query(Checkpoint).select_entity_from(inner_query)\
            #     .filter(inner_query.c.row_number == 1)\
            #     .order_by(Checkpoint.table_name.asc())
            return list(query)

    def update_checkpoint(self, run):
        with session_scope(self.Session) as session:
            session.merge(run)

    def _validate_tables(self):
        if not self.table_names:
            raise Exception("Not tables set in checkpoint manager")


class CheckpointManagerWithSince(object):
    def __init__(self, manager, since):
        self.manager = manager
        self.since_param = since

    def set_checkpoint(self, checkpoint_time, is_final=False):
        if self.manager:
            self.manager.set_checkpoint(checkpoint_time, is_final)


class CheckpointManagerProvider(object):
    def __init__(self, base_checkpoint_manager=None, since=None, start_over=None):
        self.start_over = start_over
        self.since = since
        self.base_checkpoint_manager = base_checkpoint_manager

    def get_since(self, checkpoint_manager):
        if self.start_over:
            return None

        if self.since:
            return self.since

        if checkpoint_manager:
            since = checkpoint_manager.get_time_of_last_checkpoint()
            return dateutil.parser.parse(since) if since else None

    def get_checkpoint_manager(self, table_names):
        """This get's called before each table is exported and set in the `env`. It is then
        passed to the API client and used to set the checkpoints.

        :param table_names: List of table names being exported to. This is a list since
                            multiple tables can be processed by a since API query.
        """
        manager = None
        if self.base_checkpoint_manager:
            manager = self.base_checkpoint_manager.for_tables(table_names)

        since = self.get_since(manager)

        logger.info(
            "Creating checkpoint manager for tables: %s with 'since' parameter: %s",
            ', '.join(table_names), since
        )
        return CheckpointManagerWithSince(manager, since)
