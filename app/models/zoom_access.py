# -*- coding: utf-8 -*-
"""온라인 강의실 줌 접속 로그 모델"""
from app.models import db
from datetime import datetime


class ZoomAccessLog(db.Model):
    """줌 강의실 접속 로그"""
    __tablename__ = 'zoom_access_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id'), nullable=False, index=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.course_id'), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('course_sessions.session_id'), nullable=True)

    accessed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Relationships
    student = db.relationship('Student', backref='zoom_access_logs')
    teacher = db.relationship('User', backref='zoom_access_logs', foreign_keys=[teacher_id])
    course = db.relationship('Course', backref='zoom_access_logs')
    session = db.relationship('CourseSession', backref='zoom_access_logs')

    def __repr__(self):
        return f'<ZoomAccessLog {self.log_id}: Student {self.student_id} → Teacher {self.teacher_id}>'
