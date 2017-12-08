from sqlalchemy import *


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    table = Table('commcare_export_runs', meta, autoload=True)
    if 'since_param' not in table.c:
        table.c.time_of_run.alter(name='since_param')


def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    table = Table('commcare_export_runs', meta, autoload=True)
    table.c.since_param.alter(name='time_of_run')
