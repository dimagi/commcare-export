"""rename_time_of_run_to_since_param

Revision ID: 29c27e7e2bf6
Revises: d3ce9dc9907a
Create Date: 2018-05-03 12:01:13.046003

"""
import sqlalchemy as sa
from alembic import op

revision = '29c27e7e2bf6'
down_revision = 'd3ce9dc9907a'
branch_labels = None
depends_on = None


def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    table = sa.Table('commcare_export_runs', meta, autoload=True)
    if 'since_param' not in table.c:
        op.alter_column(
            'commcare_export_runs', 'time_of_run',
            new_column_name='since_param',
            existing_type=sa.Unicode(32)
        )


def downgrade():
    op.alter_column('commcare_export_runs', 'since_param', new_column_name='time_of_run')
