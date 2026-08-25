"""add curriculum_weeks table

Revision ID: b6d2f4a19c73
Revises: d4e5f6a7b8c9
Create Date: 2026-08-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b6d2f4a19c73'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    # 이 프로젝트는 create_app()이 매번 db.create_all()도 실행하기 때문에, 새 모델을 추가하고 나면
    # 앱이 먼저 떠서 테이블을 만들어버린 뒤 이 migrate가 뒤늦게 실행되는 경우가 있음.
    # 이미 생성돼 있으면 건너뛰어 "table already exists" 충돌을 피함.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'curriculum_weeks' in inspector.get_table_names():
        return

    op.create_table(
        'curriculum_weeks',
        sa.Column('curriculum_week_id', sa.String(length=36), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('quarter', sa.String(length=20), nullable=False),
        sa.Column('grade', sa.String(length=10), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('date_range', sa.String(length=50), nullable=True),
        sa.Column('is_holiday', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('book_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['book_id'], ['books.book_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('curriculum_week_id'),
        sa.UniqueConstraint('year', 'quarter', 'grade', 'week_number', name='uq_curriculum_week'),
    )
    op.create_index('ix_curriculum_weeks_year', 'curriculum_weeks', ['year'])
    op.create_index('ix_curriculum_weeks_quarter', 'curriculum_weeks', ['quarter'])
    op.create_index('ix_curriculum_weeks_grade', 'curriculum_weeks', ['grade'])
    op.create_index('ix_curriculum_weeks_book_id', 'curriculum_weeks', ['book_id'])


def downgrade():
    op.drop_index('ix_curriculum_weeks_book_id', table_name='curriculum_weeks')
    op.drop_index('ix_curriculum_weeks_grade', table_name='curriculum_weeks')
    op.drop_index('ix_curriculum_weeks_quarter', table_name='curriculum_weeks')
    op.drop_index('ix_curriculum_weeks_year', table_name='curriculum_weeks')
    op.drop_table('curriculum_weeks')
