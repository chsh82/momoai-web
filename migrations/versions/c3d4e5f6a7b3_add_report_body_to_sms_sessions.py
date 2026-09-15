"""add report_body to sms_sessions

Revision ID: c3d4e5f6a7b3
Revises: b2c3d4e5f6a2
Create Date: 2026-09-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b3'
down_revision = 'b2c3d4e5f6a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sms_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('report_body', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('sms_sessions', schema=None) as batch_op:
        batch_op.drop_column('report_body')
