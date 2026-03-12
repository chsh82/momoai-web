"""add gender columns

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = ('a1b2c3d4e5f6', 'b2c3d4e5f6a1')
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gender', sa.String(length=10), nullable=True))

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gender', sa.String(length=10), nullable=True))


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('gender')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('gender')
