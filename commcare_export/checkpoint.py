import datetime
import logging
import uuid

import os
from contextlib import contextmanager

import dateutil.parser
from sqlalchemy import Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from commcare_export.writers import SqlMixin

logger = logging.getLogger(__name__)
repo_root = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir))

Base = declarative_base()


class ExportRun(Base):
    __tablename__ = 'commcare_export_runs'

    id = Column(String, primary_key=True)
    query_file_name = Column(String)
    query_file_md5 = Column(String)
    key = Column(String)
    project = Column(String)
    commcare = Column(String)
    since_param = Column(String)
    time_of_run = Column(String)
    final = Column(Boolean)

    def __repr__(self):
        return (
            "<ExportRun("
            "id={r.id}, "
            "query_file_name={r.query_file_name}, "
            "query_file_md5={r.query_file_md5}, "
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

    def __init__(self, db_url, query, query_md5, project, commcare, key=None, poolclass=None):
        super(CheckpointManager, self).__init__(db_url, poolclass=poolclass)
        self.query = query
        self.query_md5 = query_md5
        self.project = project
        self.commcare = commcare
        self.key = key
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def set_batch_checkpoint(self, checkpoint_time):
        self._set_checkpoint(checkpoint_time, False)

    def set_final_checkpoint(self):
        last_run = self.get_time_of_last_run()
        if last_run:
            self._set_checkpoint(dateutil.parser.parse(last_run), True)
            self._cleanup()

    def _set_checkpoint(self, checkpoint_time, final):
        logger.info('Setting %s checkpoint: %s', 'final' if final else 'batch', checkpoint_time)
        checkpoint_time = checkpoint_time or datetime.datetime.utcnow()
        with session_scope(self.Session) as session:
            session.add(ExportRun(
                id=uuid.uuid4().hex,
                query_file_name=self.query,
                query_file_md5=self.query_md5,
                key=self.key,
                project=self.project,
                commcare=self.commcare,
                since_param=checkpoint_time.isoformat(),
                time_of_run=datetime.datetime.utcnow().isoformat(),
                final=final
            ))

    def create_checkpoint_table(self, revision='head'):
        from alembic import command, config
        cfg = config.Config(os.path.join(self.migrations_repository, 'alembic.ini'))
        cfg.set_main_option('script_location', self.migrations_repository)
        with self.engine.begin() as connection:
            cfg.attributes['connection'] = connection
            command.upgrade(cfg, revision)

    def _cleanup(self):
        with session_scope(self.Session) as session:
            session.query(ExportRun).filter_by(
                final=False, query_file_md5=self.query_md5,
                project=self.project, commcare=self.commcare
            ).delete()

    def get_time_of_last_run(self):
        with session_scope(self.Session) as session:
            if self.key:
                run = self._get_last_run(
                    session, key=self.key,
                    project=self.project, commcare=self.commcare
                )
            else:
                run = self._get_last_run(
                    session, query_file_md5=self.query_md5,
                    project=self.project, commcare=self.commcare, key=self.key
                )
                if not run:
                    # Check for run without the args
                    run = self._get_last_run(session, query_file_md5=self.query_md5, key=self.key)
        return run.since_param if run else None

    def _get_last_run(self, session, **filters):
        return session.query(ExportRun).filter_by(**filters)\
            .order_by(ExportRun.since_param.desc()).first()
