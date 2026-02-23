"""add is_temp to students

Revision ID: e3f1a2b4c5d6
Revises: b6eb88b3f0cc
Create Date: 2026-02-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'e3f1a2b4c5d6'
down_revision = 'b6eb88b3f0cc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_temp', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('is_temp')
