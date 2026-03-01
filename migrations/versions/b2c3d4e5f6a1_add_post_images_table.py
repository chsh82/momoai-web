"""add post_images table for universal board image upload

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-03-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'post_images',
        sa.Column('image_id', sa.String(36), primary_key=True),
        sa.Column('board_type', sa.String(50), nullable=False, index=True),
        sa.Column('post_id', sa.String(36), nullable=False, index=True),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('stored_filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('order', sa.Integer(), default=0),
        sa.Column('uploaded_by', sa.String(36),
                  sa.ForeignKey('users.user_id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('post_images')
