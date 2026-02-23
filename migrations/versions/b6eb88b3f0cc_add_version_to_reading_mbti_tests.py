"""add version to reading_mbti_tests

Revision ID: b6eb88b3f0cc
Revises: a3b7e45b5f25
Create Date: 2026-02-21 23:46:43.785157

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6eb88b3f0cc'
down_revision = 'a3b7e45b5f25'
branch_labels = None
depends_on = None


def upgrade():
    # Both changes already applied directly; no-op to advance version
    pass


def downgrade():
    pass
