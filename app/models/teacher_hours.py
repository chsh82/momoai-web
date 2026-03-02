# -*- coding: utf-8 -*-
"""강사 시수 보정 모델"""
from datetime import datetime
from app.models import db


class TeacherHoursCorrection(db.Model):
    """관리자가 강사 월별 시수에 수동으로 가감하는 보정 레코드"""
    __tablename__ = 'teacher_hours_corrections'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.Integer, nullable=False, index=True)
    correction_date = db.Column(db.Date, nullable=True)    # 특정 날짜 or null
    course_type = db.Column(db.String(50), nullable=True)  # 특정 유형 or null
    hours_delta = db.Column(db.Float, nullable=False)      # +/- 값
    note = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='hours_corrections')
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<TeacherHoursCorrection teacher={self.teacher_id} {self.year}-{self.month:02d} delta={self.hours_delta:+.1f}>'
