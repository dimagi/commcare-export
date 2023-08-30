"""Added cursor to checkpoint

Revision ID: 3b37b3b06104
Revises: 6f158d161ab6
Create Date: 2023-08-25 11:10:38.713189

"""
from alembic import op
import sqlalchemy as sa


revision = '3b37b3b06104'
down_revision = '6f158d161ab6'
branch_labels = None
depends_on = None


def upgrade():
    url = op.get_bind().engine.url
    collation = 'utf8_bin' if 'mysql' in url.drivername else None
    op.add_column(
        'commcare_export_runs',
        sa.Column('cursor', sa.Unicode(255, collation=collation))
    )

def downgrade():
    op.drop_column('commcare_export_runs', 'cursor')
