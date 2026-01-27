"""add_back_time_of_run

Revision ID: 9945abb4ec70
Revises: 29c27e7e2bf6
Create Date: 2018-05-03 12:03:50.770411

"""
from alembic import op
import sqlalchemy as sa


revision = '9945abb4ec70'
down_revision = '29c27e7e2bf6'
branch_labels = None
depends_on = None


def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    table = sa.Table('commcare_export_runs', meta, autoload=True)
    if 'time_of_run' not in table.c:
        url = op.get_bind().engine.url
        collation = 'utf8_bin' if 'mysql' in url.drivername else None
        op.add_column(
            'commcare_export_runs',
            sa.Column('time_of_run', sa.Unicode(32, collation=collation))
        )


def downgrade():
    op.drop_column('commcare_export_runs', 'time_of_run')
