"""Add essay_id to hall_of_fame

Revision ID: ddb4a39559d8
Revises: d5e6f7a8b9c4
Create Date: 2026-09-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ddb4a39559d8'
down_revision = 'd5e6f7a8b9c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('hall_of_fame', schema=None) as batch_op:
        batch_op.add_column(sa.Column('essay_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_hall_of_fame_essay_id', ['essay_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_hall_of_fame_essay_id', 'essays', ['essay_id'], ['essay_id'],
            ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('hall_of_fame', schema=None) as batch_op:
        batch_op.drop_constraint('fk_hall_of_fame_essay_id', type_='foreignkey')
        batch_op.drop_index('ix_hall_of_fame_essay_id')
        batch_op.drop_column('essay_id')
