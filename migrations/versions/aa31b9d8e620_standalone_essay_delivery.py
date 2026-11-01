"""Standalone essay delivery and durable generations, additive only."""
from alembic import op
import sqlalchemy as sa
revision = 'aa31b9d8e620'
down_revision = '0548f00b2524'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('essay_teacher_grants',
        sa.Column('grant_id', sa.String(36), primary_key=True),
        sa.Column('essay_id', sa.String(36), sa.ForeignKey('essays.essay_id', ondelete='CASCADE'), nullable=False),
        sa.Column('teacher_id', sa.String(36), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime()),
        sa.Column('revoked_by', sa.String(36), sa.ForeignKey('users.user_id')),
        sa.Column('revoke_reason', sa.Text()),
        sa.CheckConstraint("mode IN ('reference','correction')", name='ck_essay_grant_mode'),
        sa.CheckConstraint('length(trim(reason)) > 0', name='ck_essay_grant_reason'),
        sa.CheckConstraint('(revoked_at IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL) OR '
            '(revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revoke_reason IS NOT NULL AND length(trim(revoke_reason)) > 0)',
            name='ck_essay_grant_revocation'))
    op.create_index('ix_essay_teacher_grants_essay_id', 'essay_teacher_grants', ['essay_id'])
    op.create_index('ix_essay_teacher_grants_teacher_id', 'essay_teacher_grants', ['teacher_id'])
    op.create_index('uq_essay_active_recipient_mode', 'essay_teacher_grants', ['essay_id','teacher_id','mode'],
        unique=True, sqlite_where=sa.text('revoked_at IS NULL'))
    op.create_index('uq_essay_active_correction', 'essay_teacher_grants', ['essay_id'],
        unique=True, sqlite_where=sa.text("revoked_at IS NULL AND mode = 'correction'"))
    op.create_table('essay_correction_jobs',
        sa.Column('essay_id', sa.String(36), sa.ForeignKey('essays.essay_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('job_id', sa.String(36), nullable=False),
        sa.Column('actor_id', sa.String(36), sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('revision_note', sa.Text(), nullable=True))


def downgrade():
    op.drop_table('essay_correction_jobs')
    op.drop_table('essay_teacher_grants')
