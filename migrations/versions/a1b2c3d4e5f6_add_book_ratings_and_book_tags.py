"""add book_ratings table, book tag columns, inquiry recipient_id

Revision ID: a1b2c3d4e5f6
Revises: 3bcd43f55321
Create Date: 2026-02-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '3bcd43f55321'
branch_labels = None
depends_on = None


def upgrade():
    # books 테이블에 뱃지 컬럼 추가
    with op.batch_alter_table('books', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_curriculum', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('is_recommended', sa.Boolean(), nullable=False, server_default='0'))

    # inquiry_posts 테이블에 recipient_id 컬럼 추가 (없으면)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    inq_cols = [c['name'] for c in inspector.get_columns('inquiry_posts')]
    if 'recipient_id' not in inq_cols:
        with op.batch_alter_table('inquiry_posts', schema=None) as batch_op:
            batch_op.add_column(sa.Column('recipient_id', sa.String(36), nullable=True))

    # book_ratings 테이블 생성
    op.create_table(
        'book_ratings',
        sa.Column('rating_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('book_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('fun_score', sa.Integer(), nullable=False),
        sa.Column('usefulness_score', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['book_id'], ['books.book_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('rating_id'),
        sa.UniqueConstraint('book_id', 'user_id', name='unique_book_rating')
    )
    op.create_index('ix_book_ratings_book_id', 'book_ratings', ['book_id'])
    op.create_index('ix_book_ratings_user_id', 'book_ratings', ['user_id'])


def downgrade():
    op.drop_table('book_ratings')
    with op.batch_alter_table('inquiry_posts', schema=None) as batch_op:
        batch_op.drop_column('recipient_id')
    with op.batch_alter_table('books', schema=None) as batch_op:
        batch_op.drop_column('is_recommended')
        batch_op.drop_column('is_curriculum')
