"""add_hof_comments_likes_congrats

명예의 전당 댓글·좋아요 테이블(hall_of_fame_comments/hall_of_fame_likes) 자체는
새 테이블이라 앱 시작 시 자동 생성(app/__init__.py의 db.create_all(), "앱 시작 시
누락된 테이블 자동 생성")에 맡긴다(이 저장소의 기존 관행 - d4e5f6a7b8c9 등 과거
마이그레이션도 신규 테이블은 만들지 않고 기존 테이블 컬럼 추가(add_column)만
Alembic으로 관리해왔다). 이 마이그레이션은 create_all()이 다루지 못하는 부분 -
이미 존재하는 students 테이블에 컬럼 추가 - 만 담당한다.

Revision ID: 68e9297ca685
Revises: 37d06dfd161f
Create Date: 2026-09-19 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '68e9297ca685'
down_revision = '37d06dfd161f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('hof_congrats_shown_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('hof_congrats_shown_at')
