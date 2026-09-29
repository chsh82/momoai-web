"""add consultation proposed_source_course_id and parent_confirmed_at

Revision ID: c4d8f1a2b7e5
Revises: f2b8a4c6e913
Create Date: 2026-09-29 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d8f1a2b7e5'
down_revision = 'f2b8a4c6e913'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('consultation_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('proposed_source_course_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('parent_confirmed_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key(
            'fk_consultation_requests_proposed_source_course_id',
            'courses', ['proposed_source_course_id'], ['course_id'], ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('consultation_requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_consultation_requests_proposed_source_course_id', type_='foreignkey')
        batch_op.drop_column('parent_confirmed_at')
        batch_op.drop_column('proposed_source_course_id')
