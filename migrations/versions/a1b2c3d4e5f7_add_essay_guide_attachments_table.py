"""add essay_guide_attachments table

Revision ID: a1b2c3d4e5f7
Revises: c2e4a6f8b0d1
Create Date: 2026-09-10 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = 'c2e4a6f8b0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('essay_guide_attachments',
    sa.Column('attachment_id', sa.String(length=36), nullable=False),
    sa.Column('essay_id', sa.String(length=36), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('stored_filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_type', sa.String(length=20), nullable=False),
    sa.Column('media_type', sa.String(length=100), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['essay_id'], ['essays.essay_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('attachment_id')
    )
    with op.batch_alter_table('essay_guide_attachments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_essay_guide_attachments_essay_id'), ['essay_id'], unique=False)


def downgrade():
    with op.batch_alter_table('essay_guide_attachments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_essay_guide_attachments_essay_id'))

    op.drop_table('essay_guide_attachments')
