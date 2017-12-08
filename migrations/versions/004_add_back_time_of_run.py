from sqlalchemy import *


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    table = Table('commcare_export_runs', meta, autoload=True)
    if 'time_of_run' not in table.c:
        collation = 'utf8_bin' if 'mysql' in migrate_engine.url.drivername else None
        time_of_run = Column('time_of_run', Unicode(32, collation=collation))
        time_of_run.create(table)


def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    table = Table('commcare_export_runs', meta, autoload=True)
    table.c.time_of_run.drop()
