"""Create commcare_export_runs table

Revision ID: c36489c5a628
Revises: 
Create Date: 2018-05-03 11:52:58.706727

"""
from alembic import op, context
import sqlalchemy as sa


revision = 'c36489c5a628'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    meta.reflect()
    if 'commcare_export_runs' not in meta.tables:
        url = op.get_bind().engine.url
        collation = 'utf8_bin' if 'mysql' in url.drivername else None
        op.create_table(
            'commcare_export_runs',
            sa.Column('id', sa.Unicode(64), primary_key=True),
            sa.Column('query_file_name', sa.Unicode(255, collation=collation)),
            sa.Column('query_file_md5', sa.Unicode(255, collation=collation)),
            sa.Column('time_of_run', sa.Unicode(32, collation=collation))
        )


def downgrade():
    op.drop_table('commcare_export_runs')
