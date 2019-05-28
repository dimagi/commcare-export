"""Add 'table_name' column

Revision ID: f4fd4c80f40a
Revises: d82e1d06a82c
Create Date: 2019-05-28 11:34:52.353749

"""
from alembic import op
import sqlalchemy as sa


revision = 'f4fd4c80f40a'
down_revision = 'd82e1d06a82c'
branch_labels = None
depends_on = None


def upgrade():
    url = op.get_bind().engine.url
    collation = 'utf8_bin' if 'mysql' in url.drivername else None
    op.add_column(
        'commcare_export_runs',
        sa.Column('table_name', sa.Unicode(255, collation=collation))
    )

def downgrade():
    op.drop_column('commcare_export_runs', 'table_name')
