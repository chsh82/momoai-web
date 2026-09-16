"""add tutorial_progress, tutorial_attempt, tutorial_course_reward tables

Revision ID: d5e6f7a8b9c4
Revises: c3d4e5f6a7b3
Create Date: 2026-09-15 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e6f7a8b9c4'
down_revision = 'c3d4e5f6a7b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tutorial_progress',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('track', sa.String(length=16), nullable=False),
    sa.Column('course', sa.String(length=16), nullable=False),
    sa.Column('lesson_id', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('total', sa.Integer(), nullable=True),
    sa.Column('done_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'lesson_id', name='uq_prog_user_lesson')
    )
    with op.batch_alter_table('tutorial_progress', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tutorial_progress_user_id'), ['user_id'], unique=False)

    op.create_table('tutorial_attempt',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('lesson_id', sa.String(length=32), nullable=False),
    sa.Column('question_id', sa.String(length=48), nullable=False),
    sa.Column('rule_no', sa.String(length=8), nullable=True),
    sa.Column('correct', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tutorial_attempt', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tutorial_attempt_user_id'), ['user_id'], unique=False)

    op.create_table('tutorial_course_reward',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('student_id', sa.String(length=36), nullable=False),
    sa.Column('track', sa.String(length=16), nullable=False),
    sa.Column('course', sa.String(length=16), nullable=False),
    sa.Column('points', sa.Integer(), nullable=True),
    sa.Column('rewarded_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['student_id'], ['students.student_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('student_id', 'track', 'course', name='uq_reward_student_course')
    )
    with op.batch_alter_table('tutorial_course_reward', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tutorial_course_reward_student_id'), ['student_id'], unique=False)


def downgrade():
    with op.batch_alter_table('tutorial_course_reward', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tutorial_course_reward_student_id'))
    op.drop_table('tutorial_course_reward')

    with op.batch_alter_table('tutorial_attempt', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tutorial_attempt_user_id'))
    op.drop_table('tutorial_attempt')

    with op.batch_alter_table('tutorial_progress', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tutorial_progress_user_id'))
    op.drop_table('tutorial_progress')
