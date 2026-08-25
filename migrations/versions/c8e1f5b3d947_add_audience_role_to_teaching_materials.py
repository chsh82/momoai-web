"""add audience_role to teaching_materials

Revision ID: c8e1f5b3d947
Revises: b6d2f4a19c73
Create Date: 2026-08-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c8e1f5b3d947'
down_revision = 'b6d2f4a19c73'
branch_labels = None
depends_on = None


def upgrade():
    # create_app()이 매번 db.create_all()도 실행하므로, 앱이 먼저 컬럼을 만들어버린 뒤
    # 이 migrate가 뒤늦게 실행되는 경우가 있음. 이미 있으면 건너뜀.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = [c['name'] for c in inspector.get_columns('teaching_materials')]
    if 'audience_role' in cols:
        return

    with op.batch_alter_table('teaching_materials', schema=None) as batch_op:
        batch_op.add_column(sa.Column('audience_role', sa.String(length=10), nullable=False, server_default='student'))
        batch_op.create_index(batch_op.f('ix_teaching_materials_audience_role'), ['audience_role'], unique=False)


def downgrade():
    with op.batch_alter_table('teaching_materials', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_teaching_materials_audience_role'))
        batch_op.drop_column('audience_role')
