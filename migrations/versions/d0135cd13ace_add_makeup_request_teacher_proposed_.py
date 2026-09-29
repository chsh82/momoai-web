"""add makeup request teacher proposed schedule and parent confirmation

Revision ID: d0135cd13ace
Revises: 9c4bb8868874
Create Date: 2026-09-29 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0135cd13ace'
down_revision = '9c4bb8868874'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('teacher_proposed_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('teacher_proposed_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('parent_confirmed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.drop_column('parent_confirmed_at')
        batch_op.drop_column('teacher_proposed_time')
        batch_op.drop_column('teacher_proposed_date')
