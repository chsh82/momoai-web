"""add teacher_confirmed to makeup_class_requests

Revision ID: 9c4bb8868874
Revises: 600b2e984ce8
Create Date: 2026-09-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9c4bb8868874'
down_revision = '600b2e984ce8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('teacher_confirmed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.drop_column('teacher_confirmed_at')
        batch_op.drop_column('teacher_confirmed')
