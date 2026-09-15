"""add sms_sessions and sms_messages tables

Revision ID: b2c3d4e5f6a2
Revises: a1b2c3d4e5f7
Create Date: 2026-09-15 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a2'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sms_sessions',
    sa.Column('sms_session_id', sa.String(length=36), nullable=False),
    sa.Column('course_id', sa.String(length=36), nullable=False),
    sa.Column('class_date', sa.Date(), nullable=False),
    sa.Column('teacher_id', sa.String(length=36), nullable=True),
    sa.Column('class_type', sa.String(length=20), nullable=True),
    sa.Column('book', sa.String(length=200), nullable=True),
    sa.Column('week', sa.String(length=50), nullable=True),
    sa.Column('raw_summary', sa.Text(), nullable=True),
    sa.Column('name_map', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['teacher_id'], ['users.user_id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('sms_session_id'),
    sa.UniqueConstraint('course_id', 'class_date', name='uq_sms_session_course_date')
    )
    with op.batch_alter_table('sms_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sms_sessions_course_id'), ['course_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sms_sessions_class_date'), ['class_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_sms_sessions_teacher_id'), ['teacher_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sms_sessions_created_at'), ['created_at'], unique=False)

    op.create_table('sms_messages',
    sa.Column('sms_message_id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('student_id', sa.String(length=36), nullable=True),
    sa.Column('student_name', sa.String(length=100), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('msg_type', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['session_id'], ['sms_sessions.sms_session_id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['students.student_id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('sms_message_id')
    )
    with op.batch_alter_table('sms_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sms_messages_session_id'), ['session_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sms_messages_student_id'), ['student_id'], unique=False)


def downgrade():
    with op.batch_alter_table('sms_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sms_messages_student_id'))
        batch_op.drop_index(batch_op.f('ix_sms_messages_session_id'))
    op.drop_table('sms_messages')

    with op.batch_alter_table('sms_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sms_sessions_created_at'))
        batch_op.drop_index(batch_op.f('ix_sms_sessions_teacher_id'))
        batch_op.drop_index(batch_op.f('ix_sms_sessions_class_date'))
        batch_op.drop_index(batch_op.f('ix_sms_sessions_course_id'))
    op.drop_table('sms_sessions')
