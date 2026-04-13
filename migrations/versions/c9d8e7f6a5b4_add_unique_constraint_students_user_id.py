"""add unique constraint to students.user_id

Revision ID: c9d8e7f6a5b4
Revises: (3bcd43f55321, e1f2a3b4c5d6)
Create Date: 2026-04-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9d8e7f6a5b4'
down_revision = ('3bcd43f55321', 'e1f2a3b4c5d6')
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_students_user_id', ['user_id'])


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_constraint('uq_students_user_id', type_='unique')
