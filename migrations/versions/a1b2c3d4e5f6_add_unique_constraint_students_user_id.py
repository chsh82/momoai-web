"""add unique constraint to students.user_id

Revision ID: a1b2c3d4e5f6
Revises: f7441b089d4e
Create Date: 2026-04-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f7441b089d4e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_students_user_id', ['user_id'])


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_constraint('uq_students_user_id', type_='unique')
