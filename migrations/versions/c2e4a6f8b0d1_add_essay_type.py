"""add essay_type to essays

Revision ID: c2e4a6f8b0d1
Revises: b7c1f2a9d4e0
Create Date: 2026-08-29 00:00:00.000000

과제 업로드 시 유형(기본과제글/리라이팅/기타)을 선택하게 하고, 마일리지
RW01/RW02 지급과 BG01/BG03 뱃지 조건을 이 값으로 분기하기 위해 추가함.
기존 첨삭 건(essays 테이블에 이미 쌓여 있는 데이터)은 전부 'basic'으로
채워야 하므로 server_default를 반드시 넣는다 - 이게 없으면 SQLite에서
NOT NULL 컬럼 추가 시 기존 행에 대해 백필이 안 되어 마이그레이션이
실패한다. create_all()이 먼저 컬럼을 만들어버리는 경우를 대비해 기존
마일리지 마이그레이션과 동일하게 존재 여부를 확인하고 건너뛴다.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2e4a6f8b0d1'
down_revision = 'b7c1f2a9d4e0'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('essays')}

    if 'essay_type' not in existing_columns:
        with op.batch_alter_table('essays') as batch_op:
            batch_op.add_column(sa.Column('essay_type', sa.String(length=20),
                                          nullable=False, server_default='basic'))


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {c['name'] for c in inspector.get_columns('essays')}

    if 'essay_type' in existing_columns:
        with op.batch_alter_table('essays') as batch_op:
            batch_op.drop_column('essay_type')
