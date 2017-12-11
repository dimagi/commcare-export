from sqlalchemy import *

def _get_table(meta):
    collation = 'utf8_bin' if 'mysql' in meta.bind.url.drivername else None
    return Table(
        'commcare_export_runs',
        meta,
        Column('id', Unicode(64), primary_key=True),
        Column('query_file_name', Unicode(255, collation=collation)),
        Column('query_file_md5', Unicode(32, collation=collation)),
        Column('time_of_run', Unicode(32, collation=collation)),
    )


def upgrade(migrate_engine):
    # user separate metadata otherwise it thinks the table exists
    tmp_meta = MetaData(bind=migrate_engine)
    tmp_meta.reflect()

    # don't make metadata module level otherwise tests fail since meta
    # get's bound multiple times
    table = _get_table(MetaData(bind=migrate_engine))
    if table.name not in tmp_meta.tables:
        table.create(migrate_engine)


def downgrade(migrate_engine):
    _get_table(MetaData(bind=migrate_engine)).drop()

