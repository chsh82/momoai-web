"""add participation and comprehension score to attendance

Revision ID: 812fc1f4c175
Revises: f7441b089d4e
Create Date: 2026-02-24 09:21:00.534425

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '812fc1f4c175'
down_revision = 'f7441b089d4e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('participation_score', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('comprehension_score', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.drop_column('comprehension_score')
        batch_op.drop_column('participation_score')

    # ### end Alembic commands ###
