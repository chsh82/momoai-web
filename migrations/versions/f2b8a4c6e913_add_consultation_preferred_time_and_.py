"""add consultation preferred_time and created_makeup_course_id

Revision ID: f2b8a4c6e913
Revises: a7c3e91f5b2d
Create Date: 2026-09-29 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2b8a4c6e913'
down_revision = 'a7c3e91f5b2d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('consultation_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preferred_time', sa.Time(), nullable=True))
        batch_op.add_column(sa.Column('created_makeup_course_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_consultation_requests_created_makeup_course_id',
            'courses', ['created_makeup_course_id'], ['course_id'], ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('consultation_requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_consultation_requests_created_makeup_course_id', type_='foreignkey')
        batch_op.drop_column('created_makeup_course_id')
        batch_op.drop_column('preferred_time')
