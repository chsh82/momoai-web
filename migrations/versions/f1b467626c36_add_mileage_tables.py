"""add mileage tables

Revision ID: f1b467626c36
Revises: d391a7c4e8b2
Create Date: 2026-08-28 13:48:26.003093

이 프로젝트는 create_app()이 매번 db.create_all()도 실행하기 때문에, 새 모델을
추가하고 나면 앱이 먼저 떠서 테이블을 만들어버린 뒤 이 migrate가 뒤늦게
실행되는 경우가 있음. 이미 생성돼 있으면 건너뛰어 "table/column already
exists" 충돌을 피한다(b6d2f4a19c73_add_curriculum_weeks_table.py와 동일 패턴).

autogenerate가 원래 감지했던 hall_of_fame_views/essay_reports 테이블
drop_table과 관련 drop_index는 이 작업(마일리지 기능)과 무관한 기존 스키마
드리프트(모델은 이미 삭제됐지만 실제 DB에는 남아있던 테이블)라서 전부
제거했다. 이 파일에는 마일리지 관련 create_table/add_column만 남긴다.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1b467626c36'
down_revision = 'd391a7c4e8b2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'point_events' not in existing_tables:
        op.create_table(
            'point_events',
            sa.Column('event_id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.String(length=36), nullable=False),
            sa.Column('activity_code', sa.String(length=10), nullable=False),
            sa.Column('entry_type', sa.String(length=10), nullable=False),
            sa.Column('points', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=10), nullable=False),
            sa.Column('source_type', sa.String(length=30), nullable=False),
            sa.Column('source_id', sa.String(length=64), nullable=False),
            sa.Column('season', sa.String(length=7), nullable=False),
            sa.Column('occurred_at', sa.DateTime(), nullable=False),
            sa.Column('confirmed_at', sa.DateTime(), nullable=True),
            sa.Column('cancelled_at', sa.DateTime(), nullable=True),
            sa.Column('cancel_reason', sa.String(length=200), nullable=True),
            sa.Column('related_event_id', sa.Integer(), nullable=True),
            sa.Column('granted_by', sa.String(length=36), nullable=True),
            sa.Column('memo', sa.String(length=200), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['student_id'], ['students.student_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['related_event_id'], ['point_events.event_id']),
            sa.ForeignKeyConstraint(['granted_by'], ['users.user_id']),
            sa.PrimaryKeyConstraint('event_id'),
            sa.UniqueConstraint('student_id', 'activity_code', 'source_type', 'source_id', 'entry_type',
                               name='uq_point_event_source'),
        )
        op.create_index('ix_point_event_student_season', 'point_events', ['student_id', 'season'])
        op.create_index('ix_point_event_season_status', 'point_events', ['season', 'status'])
        op.create_index('ix_point_event_source', 'point_events', ['source_type', 'source_id'])

    if 'badges' not in existing_tables:
        op.create_table(
            'badges',
            sa.Column('badge_code', sa.String(length=10), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=200), nullable=False),
            sa.Column('category', sa.String(length=10), nullable=False),
            sa.Column('icon_path', sa.String(length=200), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('is_repeatable', sa.Boolean(), nullable=False),
            sa.Column('rule_type', sa.String(length=30), nullable=False),
            sa.Column('rule_config', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint('badge_code'),
        )

    if 'student_badges' not in existing_tables:
        op.create_table(
            'student_badges',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.String(length=36), nullable=False),
            sa.Column('badge_code', sa.String(length=10), nullable=False),
            sa.Column('earned_count', sa.Integer(), nullable=False),
            sa.Column('first_earned_at', sa.DateTime(), nullable=False),
            sa.Column('last_earned_at', sa.DateTime(), nullable=False),
            sa.Column('granted_by', sa.String(length=36), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['student_id'], ['students.student_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['badge_code'], ['badges.badge_code']),
            sa.ForeignKeyConstraint(['granted_by'], ['users.user_id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('student_id', 'badge_code', name='uq_student_badge'),
        )

    if 'monthly_rankings' not in existing_tables:
        op.create_table(
            'monthly_rankings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('season', sa.String(length=7), nullable=False),
            sa.Column('level_group', sa.String(length=20), nullable=False),
            sa.Column('student_id', sa.String(length=36), nullable=False),
            sa.Column('rank', sa.Integer(), nullable=False),
            sa.Column('points', sa.Integer(), nullable=False),
            sa.Column('is_final', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['student_id'], ['students.student_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('season', 'level_group', 'student_id', name='uq_monthly_ranking'),
        )

    if 'mileage_consents' not in existing_tables:
        op.create_table(
            'mileage_consents',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.String(length=36), nullable=False),
            sa.Column('consent_type', sa.String(length=1), nullable=False),
            sa.Column('is_agreed', sa.Boolean(), nullable=False),
            sa.Column('agreed_by_user_id', sa.String(length=36), nullable=False),
            sa.Column('agreed_by_relation', sa.String(length=10), nullable=False),
            sa.Column('doc_version', sa.String(length=10), nullable=False),
            sa.Column('agreed_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['student_id'], ['students.student_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['agreed_by_user_id'], ['users.user_id']),
            sa.PrimaryKeyConstraint('id'),
        )

    comment_cols = [c['name'] for c in inspector.get_columns('comments')]
    with op.batch_alter_table('comments', schema=None) as batch_op:
        if 'is_deleted' not in comment_cols:
            batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
        if 'deleted_at' not in comment_cols:
            batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    op.drop_table('mileage_consents')

    op.drop_table('monthly_rankings')

    op.drop_table('student_badges')

    op.drop_table('badges')

    op.drop_index('ix_point_event_source', table_name='point_events')
    op.drop_index('ix_point_event_season_status', table_name='point_events')
    op.drop_index('ix_point_event_student_season', table_name='point_events')
    op.drop_table('point_events')
