"""add args columns for project and commcare url

Revision ID: 53f1aad98e33
Revises: 9945abb4ec70
Create Date: 2018-08-14 12:39:55.543173

"""
from alembic import op
import sqlalchemy as sa


revision = '53f1aad98e33'
down_revision = '9945abb4ec70'
branch_labels = None
depends_on = None


def upgrade():
    url = op.get_bind().engine.url
    collation = 'utf8_bin' if 'mysql' in url.drivername else None
    op.add_column(
        'commcare_export_runs',
        sa.Column('project', sa.Unicode(32, collation=collation))
    )
    op.add_column(
        'commcare_export_runs',
        sa.Column('commcare', sa.Unicode(255, collation=collation))
    )

def downgrade():
    op.drop_column('commcare_export_runs', 'project')
    op.drop_column('commcare_export_runs', 'commcare')
