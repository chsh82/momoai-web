# -*- coding: utf-8 -*-
"""모모의 책장 - 분기별/학년별 주차 커리큘럼. 실제 도서 정보는 books 테이블을 참조함."""
import uuid
from datetime import datetime
from app.models import db


class CurriculumWeek(db.Model):
    __tablename__ = 'curriculum_weeks'

    curriculum_week_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    year = db.Column(db.Integer, nullable=False, index=True)
    quarter = db.Column(db.String(20), nullable=False, index=True)
    grade = db.Column(db.String(10), nullable=False, index=True)  # 초1~고3
    week_number = db.Column(db.Integer, nullable=False)
    date_range = db.Column(db.String(50), nullable=True)
    is_holiday = db.Column(db.Boolean, default=False, nullable=False)
    note = db.Column(db.Text, nullable=True)  # 휴강 사유 등 도서와 무관한 메모
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id', ondelete='SET NULL'),
                        nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book = db.relationship('Book', backref='curriculum_weeks')

    __table_args__ = (
        db.UniqueConstraint('year', 'quarter', 'grade', 'week_number', name='uq_curriculum_week'),
    )

    def __repr__(self):
        return f'<CurriculumWeek {self.year} {self.quarter} {self.grade} W{self.week_number}>'
