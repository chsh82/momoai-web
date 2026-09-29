"""add teacher schedule confirm fields to makeup and consultation requests

Revision ID: a7c3e91f5b2d
Revises: d0135cd13ace
Create Date: 2026-09-29 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c3e91f5b2d'
down_revision = 'd0135cd13ace'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('admin_ask_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('admin_ask_time', sa.Time(), nullable=True))

    with op.batch_alter_table('consultation_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('admin_ask_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('admin_ask_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('teacher_proposed_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('teacher_proposed_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('teacher_confirmed', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('teacher_confirmed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('consultation_requests', schema=None) as batch_op:
        batch_op.drop_column('teacher_confirmed_at')
        batch_op.drop_column('teacher_confirmed')
        batch_op.drop_column('teacher_proposed_time')
        batch_op.drop_column('teacher_proposed_date')
        batch_op.drop_column('admin_ask_time')
        batch_op.drop_column('admin_ask_date')

    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.drop_column('admin_ask_time')
        batch_op.drop_column('admin_ask_date')
