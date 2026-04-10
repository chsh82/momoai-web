"""add zoom_id to users

Revision ID: d1e2f3a4b5c6
Revises: b3c4d5e6f7a8
Create Date: 2026-04-10

"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('zoom_id', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('zoom_id')
