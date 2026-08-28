"""add student nickname

Revision ID: a4d6e9f1c8b3
Revises: f1b467626c36
Create Date: 2026-08-28 23:10:00.000000

4단계(화면) 작업 중 랭킹 표시용 닉네임 필드가 필요해 추가함(정책 문서상
"닉네임"이 요구되지만 기존 스키마에는 이 필드가 없었음). create_all()이
먼저 컬럼을 만들어버리는 경우를 대비해 기존 마일리지 마이그레이션과
동일하게 존재 여부를 확인하고 건너뛴다.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4d6e9f1c8b3'
down_revision = 'f1b467626c36'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('students')}

    if 'nickname' not in existing_columns:
        with op.batch_alter_table('students') as batch_op:
            batch_op.add_column(sa.Column('nickname', sa.String(length=20), nullable=True))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('students')}

    if 'nickname' in existing_columns:
        with op.batch_alter_table('students') as batch_op:
            batch_op.drop_column('nickname')
