"""add hermes command logs table

Revision ID: 0548f00b2524
Revises: e8f3a91c2d4b
Create Date: 2026-10-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0548f00b2524'
down_revision = 'e8f3a91c2d4b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'hermes_command_logs',
        sa.Column('log_id', sa.String(length=36), nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('admin_user_id', sa.String(length=36), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('parsed_action', sa.Text(), nullable=True),
        sa.Column('action_type', sa.String(length=30), nullable=True),
        sa.Column('resolved_params', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('clarification_question', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('error_detail', sa.Text(), nullable=True),
        sa.Column('related_entity_type', sa.String(length=50), nullable=True),
        sa.Column('related_entity_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_user_id'], ['users.user_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('log_id'),
    )
    with op.batch_alter_table('hermes_command_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_hermes_command_logs_thread_id'), ['thread_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_hermes_command_logs_admin_user_id'), ['admin_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_hermes_command_logs_action_type'), ['action_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_hermes_command_logs_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_hermes_command_logs_created_at'), ['created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('hermes_command_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_hermes_command_logs_created_at'))
        batch_op.drop_index(batch_op.f('ix_hermes_command_logs_status'))
        batch_op.drop_index(batch_op.f('ix_hermes_command_logs_action_type'))
        batch_op.drop_index(batch_op.f('ix_hermes_command_logs_admin_user_id'))
        batch_op.drop_index(batch_op.f('ix_hermes_command_logs_thread_id'))
    op.drop_table('hermes_command_logs')
