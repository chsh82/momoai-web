"""add target_student_id to assignments

Revision ID: a3b7e45b5f25
Revises: c95c6859ee55
Create Date: 2026-02-21 16:45:56.753577

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b7e45b5f25'
down_revision = 'c95c6859ee55'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assignments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_student_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_assignments_target_student_id'), ['target_student_id'], unique=False)


def downgrade():
    with op.batch_alter_table('assignments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assignments_target_student_id'))
        batch_op.drop_column('target_student_id')
