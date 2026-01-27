"""add key column

Revision ID: d82e1d06a82c
Revises: 53f1aad98e33
Create Date: 2018-08-15 12:08:51.720796

"""
from alembic import op
import sqlalchemy as sa


revision = 'd82e1d06a82c'
down_revision = '53f1aad98e33'
branch_labels = None
depends_on = None


def upgrade():
    url = op.get_bind().engine.url
    collation = 'utf8_bin' if 'mysql' in url.drivername else None
    op.add_column(
        'commcare_export_runs',
        sa.Column('key', sa.Unicode(255, collation=collation))
    )

def downgrade():
    op.drop_column('commcare_export_runs', 'key')
