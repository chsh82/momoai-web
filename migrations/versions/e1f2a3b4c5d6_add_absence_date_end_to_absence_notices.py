"""add absence_date_end to absence_notices

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-04-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('absence_notices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('absence_date_end', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('absence_notices', schema=None) as batch_op:
        batch_op.drop_column('absence_date_end')
