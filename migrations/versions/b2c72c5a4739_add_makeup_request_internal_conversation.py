"""add internal_conversation_id to makeup_class_requests

Revision ID: b2c72c5a4739
Revises: 68e9297ca685
Create Date: 2026-09-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c72c5a4739'
down_revision = '68e9297ca685'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('internal_conversation_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_makeup_class_requests_internal_conversation_id',
            'conversations', ['internal_conversation_id'], ['conversation_id'],
            ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('makeup_class_requests', schema=None) as batch_op:
        batch_op.drop_constraint('fk_makeup_class_requests_internal_conversation_id', type_='foreignkey')
        batch_op.drop_column('internal_conversation_id')
