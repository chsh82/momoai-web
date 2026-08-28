"""add student_badges memo

Revision ID: b7c1f2a9d4e0
Revises: a4d6e9f1c8b3
Create Date: 2026-08-29 10:00:00.000000

4-2(관리자·강사 화면) 작업 중 BG09(장원) 수동 수여 시 "회차 정보를 메모로
입력받는다"는 지시서 요구사항에 맞는 컬럼이 없어 추가함. 기존 마일리지
마이그레이션과 동일하게 존재 여부를 확인하고 건너뛴다.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c1f2a9d4e0'
down_revision = 'a4d6e9f1c8b3'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('student_badges')}

    if 'memo' not in existing_columns:
        with op.batch_alter_table('student_badges') as batch_op:
            batch_op.add_column(sa.Column('memo', sa.String(length=200), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('student_badges')}

    if 'memo' in existing_columns:
        with op.batch_alter_table('student_badges') as batch_op:
            batch_op.drop_column('memo')
