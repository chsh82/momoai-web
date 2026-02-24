# -*- coding: utf-8 -*-
"""Attendance 모델"""
from datetime import datetime
import uuid
from app.models import db


class Attendance(db.Model):
    """출석 모델"""
    __tablename__ = 'attendance'

    attendance_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(db.String(36), db.ForeignKey('course_sessions.session_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    enrollment_id = db.Column(db.String(36), db.ForeignKey('course_enrollments.enrollment_id', ondelete='CASCADE'),
                             nullable=False, index=True)

    # 출석 상태
    status = db.Column(db.String(20), default='absent', index=True)  # present, absent, late, excused

    # 출석 체크 정보
    checked_at = db.Column(db.DateTime, nullable=True)
    checked_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))

    # 체크인 방법 (주로 manual)
    checkin_method = db.Column(db.String(20), default='manual')  # manual, system

    # 주관 평가 별점 (1~5, 기본값 3)
    participation_score = db.Column(db.Integer, default=3, nullable=True)  # 참여도
    comprehension_score = db.Column(db.Integer, default=3, nullable=True)  # 이해도

    # 비고
    notes = db.Column(db.Text, nullable=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    session = db.relationship('CourseSession', back_populates='attendance_records')
    student = db.relationship('Student', backref='attendance_records')
    enrollment = db.relationship('CourseEnrollment', backref='attendance_records')
    checker = db.relationship('User', foreign_keys=[checked_by])

    def __repr__(self):
        return f'<Attendance {self.student_id} - {self.status}>'

    def __init__(self, **kwargs):
        super(Attendance, self).__init__(**kwargs)
        if not self.attendance_id:
            self.attendance_id = str(uuid.uuid4())

    @property
    def is_present(self):
        """출석 여부"""
        return self.status in ['present', 'late']

    @property
    def is_absent(self):
        """결석 여부"""
        return self.status == 'absent'

    @property
    def is_checked(self):
        """체크 완료 여부"""
        return self.checked_at is not None
