"""add link_url and link_text to announcements

Revision ID: 37d06dfd161f
Revises: ddb4a39559d8
Create Date: 2026-09-18 02:09:39.557164

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '37d06dfd161f'
down_revision = 'ddb4a39559d8'
branch_labels = None
depends_on = None


def upgrade():
    # 자동생성 결과에서 announcements 컬럼 추가 외 나머지(essay_reports/hall_of_fame_views
    # 테이블 삭제)는 로컬 개발 DB가 모델과 어긋나 있어(db.create_all() 드리프트,
    # 기존에 알려진 이슈) 잘못 잡힌 것 - essay_reports는 운영 데이터 보존을 위해
    # 일부러 남겨둔 테이블이라 전부 제거하고 실제 변경분만 남김.
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('link_url', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('link_text', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.drop_column('link_text')
        batch_op.drop_column('link_url')
