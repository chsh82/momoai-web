"""add_week_book_to_hall_of_fame

Revision ID: f3a1b2c4d5e6
Revises: a4b5c6d7e8f9
Create Date: 2026-08-21 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f3a1b2c4d5e6'
down_revision = 'a4b5c6d7e8f9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('hall_of_fame', schema=None) as batch_op:
        batch_op.add_column(sa.Column('week_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('book_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_hall_of_fame_book_id'), ['book_id'], unique=False)
        batch_op.create_foreign_key('fk_hall_of_fame_book_id', 'books', ['book_id'], ['book_id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('hall_of_fame', schema=None) as batch_op:
        batch_op.drop_constraint('fk_hall_of_fame_book_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_hall_of_fame_book_id'))
        batch_op.drop_column('book_id')
        batch_op.drop_column('week_number')
