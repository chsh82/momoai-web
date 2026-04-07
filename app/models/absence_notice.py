# -*- coding: utf-8 -*-
"""결석 예고 모델"""
import uuid
from datetime import datetime
from app.models import db


class AbsenceNotice(db.Model):
    """결석 예고 모델 - 학생/학부모가 수업 전 결석을 미리 알리는 기능"""
    __tablename__ = 'absence_notices'

    notice_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    absence_date = db.Column(db.Date, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=False)
    notice_type = db.Column(db.String(20), default='absent')  # absent, late
    submitted_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                             nullable=True)  # 제출한 사용자 (학생 or 학부모)

    # 강사 확인 여부
    teacher_confirmed = db.Column(db.Boolean, default=False)
    teacher_confirmed_at = db.Column(db.DateTime, nullable=True)

    # 상태: pending(미확인) → confirmed(강사확인) / cancelled(취소)
    status = db.Column(db.String(20), default='pending', index=True)

    # 연결된 보강 신청 ID (보강 신청 시 연결)
    linked_makeup_request_id = db.Column(db.String(36), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    student = db.relationship('Student', backref='absence_notices')
    course = db.relationship('Course', backref='absence_notices')
    submitter = db.relationship('User', foreign_keys=[submitted_by])

    def __repr__(self):
        return f'<AbsenceNotice {self.notice_id} - {self.student_id} - {self.absence_date}>'

    @property
    def notice_type_label(self):
        return '결석' if self.notice_type == 'absent' else '지각'

    @property
    def status_label(self):
        labels = {'pending': '미확인', 'confirmed': '확인완료', 'cancelled': '취소'}
        return labels.get(self.status, self.status)
