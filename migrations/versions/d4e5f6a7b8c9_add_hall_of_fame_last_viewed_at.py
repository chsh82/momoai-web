"""add_hall_of_fame_last_viewed_at

Revision ID: d4e5f6a7b8c9
Revises: f3a1b2c4d5e6
Create Date: 2026-08-21 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'f3a1b2c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hall_of_fame_last_viewed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('hall_of_fame_last_viewed_at')
