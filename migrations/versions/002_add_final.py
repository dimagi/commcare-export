from sqlalchemy import *


def upgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    table = Table('commcare_export_runs', meta, autoload=True)
    if 'final' not in table.c:
        final = Column('final', Boolean())
        final.create(table)


def downgrade(migrate_engine):
    meta = MetaData(bind=migrate_engine)
    table = Table('commcare_export_runs', meta, autoload=True)
    table.c.final.drop()

