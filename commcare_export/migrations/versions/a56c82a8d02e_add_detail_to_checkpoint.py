"""Add detail to checkpoint

Revision ID: a56c82a8d02e
Revises: f4fd4c80f40a
Create Date: 2021-01-22 16:35:07.063082

"""
from alembic import op
import sqlalchemy as sa


revision = 'a56c82a8d02e'
down_revision = 'f4fd4c80f40a'
branch_labels = None
depends_on = None


def upgrade():
    url = op.get_bind().engine.url
    collation = 'utf8_bin' if 'mysql' in url.drivername else None
    op.add_column(
        'commcare_export_runs',
        sa.Column('data_source', sa.Unicode(255, collation=collation))
    )
    op.add_column(
        'commcare_export_runs',
        sa.Column('last_doc_id', sa.Unicode(255, collation=collation))
    )

def downgrade():
    op.drop_column('commcare_export_runs', 'data_source')
    op.drop_column('commcare_export_runs', 'last_doc_id')
