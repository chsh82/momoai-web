# -*- coding: utf-8 -*-
"""입반/전반 예약 모델"""
import uuid
from datetime import datetime
from app.models import db


class EnrollmentSchedule(db.Model):
    """입반/전반 예약 모델 - 관리자가 입력, 강사가 확인"""
    __tablename__ = 'enrollment_schedules'

    schedule_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    # enroll: 입반, withdraw: 전반
    schedule_type = db.Column(db.String(20), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)
    memo = db.Column(db.Text, nullable=True)  # 강사에게 전달할 메모

    # 상태
    status = db.Column(db.String(20), default='scheduled', index=True)
    applied_at = db.Column(db.DateTime, nullable=True)

    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                           nullable=True)

    # 알림 발송 여부
    teacher_notified = db.Column(db.Boolean, default=False)
    teacher_notified_at = db.Column(db.DateTime, nullable=True)

    # 강사 확인 여부
    teacher_confirmed = db.Column(db.Boolean, default=False)
    teacher_confirmed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='enrollment_schedules')
    course = db.relationship('Course', backref='enrollment_schedules')
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<EnrollmentSchedule {self.schedule_id} - {self.schedule_type} - {self.scheduled_date}>'

    @property
    def type_label(self):
        return '입반' if self.schedule_type == 'enroll' else '전반'

    @property
    def status_label(self):
        labels = {'scheduled': '예정', 'applied': '적용완료', 'cancelled': '취소'}
        return labels.get(self.status, self.status)
