"""add curriculum_sequence to teaching_materials

Revision ID: d391a7c4e8b2
Revises: c8e1f5b3d947
Create Date: 2026-08-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd391a7c4e8b2'
down_revision = 'c8e1f5b3d947'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('teaching_materials')]
    if 'curriculum_sequence' in cols:
        return

    with op.batch_alter_table('teaching_materials', schema=None) as batch_op:
        batch_op.add_column(sa.Column('curriculum_sequence', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('teaching_materials', schema=None) as batch_op:
        batch_op.drop_column('curriculum_sequence')
