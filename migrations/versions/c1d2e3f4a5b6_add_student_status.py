"""add student status

Revision ID: c1d2e3f4a5b6
Revises: f137914464cc
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa

revision = 'c1d2e3f4a5b6'
down_revision = 'f137914464cc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='active'))
        batch_op.add_column(sa.Column('status_changed_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_students_status', ['status'], unique=False)


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_index('ix_students_status')
        batch_op.drop_column('status_changed_at')
        batch_op.drop_column('status')
