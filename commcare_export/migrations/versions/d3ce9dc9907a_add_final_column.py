"""add final column

Revision ID: d3ce9dc9907a
Revises: c36489c5a628
Create Date: 2018-05-03 11:58:18.995223

"""
from alembic import op
import sqlalchemy as sa

revision = 'd3ce9dc9907a'
down_revision = 'c36489c5a628'
branch_labels = None
depends_on = None


def upgrade():
    meta = sa.MetaData(bind=op.get_bind())
    table = sa.Table('commcare_export_runs', meta, autoload=True)
    if 'final' not in table.c:
        op.add_column('commcare_export_runs', sa.Column('final', sa.Boolean()))


def downgrade():
    op.drop_column('commcare_export_runs', 'final')
