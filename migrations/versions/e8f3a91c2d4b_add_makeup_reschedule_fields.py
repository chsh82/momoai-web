"""add makeup request parent reschedule fields

Revision ID: e8f3a91c2d4b
Revises: c4d8f1a2b7e5
Create Date: 2026-10-09 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8f3a91c2d4b'
down_revision = 'c4d8f1a2b7e5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_reschedule_requested_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('parent_reschedule_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('parent_reschedule_admin_acted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.drop_column('parent_reschedule_admin_acted_at')
        batch_op.drop_column('parent_reschedule_reason')
        batch_op.drop_column('parent_reschedule_requested_at')
