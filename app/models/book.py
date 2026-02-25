# -*- coding: utf-8 -*-
"""도서 관련 모델"""
from datetime import datetime
from app.models import db


class Book(db.Model):
    """도서 모델"""
    __tablename__ = 'books'

    book_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False, index=True)
    author = db.Column(db.String(200), nullable=True, index=True)
    publisher = db.Column(db.String(200), nullable=True)
    isbn = db.Column(db.String(20), nullable=True, index=True)
    publication_year = db.Column(db.Integer, nullable=True)
    category = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    recommendation_reason = db.Column(db.Text, nullable=True)
    cover_image_url = db.Column(db.String(500), nullable=True)
    is_curriculum = db.Column(db.Boolean, default=False, nullable=False)   # 수업도서 뱃지
    is_recommended = db.Column(db.Boolean, default=False, nullable=False)  # 추천도서 뱃지
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='books')
    essay_relations = db.relationship('EssayBook', back_populates='book',
                                     cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Book {self.book_id} - {self.title}>'

    def __init__(self, **kwargs):
        super(Book, self).__init__(**kwargs)
        if not self.book_id:
            import uuid
            self.book_id = str(uuid.uuid4())

    # Ratings relationship
    ratings = db.relationship('BookRating', back_populates='book',
                              cascade='all, delete-orphan')

    @property
    def essay_count(self):
        """이 도서를 참고한 첨삭 수"""
        return len(self.essay_relations)

    @property
    def avg_fun_score(self):
        """학생 재미 평균 점수"""
        scores = [r.fun_score for r in self.ratings]
        return round(sum(scores) / len(scores), 1) if scores else None

    @property
    def avg_usefulness_score(self):
        """학생 유익함 평균 점수"""
        scores = [r.usefulness_score for r in self.ratings]
        return round(sum(scores) / len(scores), 1) if scores else None

    @property
    def avg_score(self):
        """평균 별점 = (재미 평균 + 유익함 평균) / 2 (학생만 반영)"""
        if not self.ratings:
            return None
        total = sum(r.fun_score + r.usefulness_score for r in self.ratings)
        return round(total / (len(self.ratings) * 2), 1)

    @property
    def rating_count(self):
        """평점 참여 학생 수"""
        return len(self.ratings)


class BookRating(db.Model):
    """도서 평점 모델 (학생만 작성 가능)"""
    __tablename__ = 'book_ratings'

    rating_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    fun_score = db.Column(db.Integer, nullable=False)          # 재미 1-5
    usefulness_score = db.Column(db.Integer, nullable=False)   # 유익함 1-5
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('book_id', 'user_id', name='unique_book_rating'),
    )

    user = db.relationship('User', foreign_keys=[user_id])
    book = db.relationship('Book', back_populates='ratings')

    def __repr__(self):
        return f'<BookRating book={self.book_id} user={self.user_id}>'


class EssayBook(db.Model):
    """첨삭-도서 관계 모델"""
    __tablename__ = 'essay_books'

    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                        primary_key=True)
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id', ondelete='CASCADE'),
                       primary_key=True)
    relation_type = db.Column(db.String(50), default='reference')
    # relation_type: reference(참고), citation(인용), inspiration(영감)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    essay = db.relationship('Essay', backref='book_relations')
    book = db.relationship('Book', back_populates='essay_relations')

    def __repr__(self):
        return f'<EssayBook {self.essay_id} - {self.book_id}>'
