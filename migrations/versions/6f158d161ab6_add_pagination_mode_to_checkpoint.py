"""Add pagination_mode to checkpoint

Revision ID: 6f158d161ab6
Revises: a56c82a8d02e
Create Date: 2021-01-25 15:13:45.996453

"""
from alembic import op
import sqlalchemy as sa


revision = '6f158d161ab6'
down_revision = 'a56c82a8d02e'
branch_labels = None
depends_on = None



def upgrade():
    url = op.get_bind().engine.url
    collation = 'utf8_bin' if 'mysql' in url.drivername else None
    op.add_column(
        'commcare_export_runs',
        sa.Column('pagination_mode', sa.Unicode(255, collation=collation))
    )

def downgrade():
    op.drop_column('commcare_export_runs', 'pagination_mode')
