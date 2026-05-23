"""add_status_to_ocr_history

Revision ID: a4b5c6d7e8f9
Revises: c9d8e7f6a5b4
Create Date: 2026-05-22 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a4b5c6d7e8f9'
down_revision = 'c9d8e7f6a5b4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ocr_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='completed'))


def downgrade():
    with op.batch_alter_table('ocr_history', schema=None) as batch_op:
        batch_op.drop_column('status')
