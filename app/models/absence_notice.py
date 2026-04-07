# -*- coding: utf-8 -*-
"""결석 예고 모델"""
import uuid
from datetime import datetime
from app.models import db


class AbsenceNotice(db.Model):
    """결석 예고 모델
    - 강사 또는 관리자가 입력
    - 입력자가 강사이면 → 관리자에게 알림, 관리자가 확인
    - 입력자가 관리자이면 → 해당 강사에게 알림, 강사가 확인
    """
    __tablename__ = 'absence_notices'

    notice_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    absence_date = db.Column(db.Date, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=False)
    notice_type = db.Column(db.String(20), default='absent')  # absent, late

    # 입력자 정보
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                           nullable=True)
    created_by_role = db.Column(db.String(20), nullable=True)  # 'admin' or 'teacher'

    # 강사 확인 (관리자가 입력한 경우 강사가 확인)
    teacher_confirmed = db.Column(db.Boolean, default=False)
    teacher_confirmed_at = db.Column(db.DateTime, nullable=True)

    # 관리자 확인 (강사가 입력한 경우 관리자가 확인)
    admin_confirmed = db.Column(db.Boolean, default=False)
    admin_confirmed_at = db.Column(db.DateTime, nullable=True)
    admin_confirmed_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                                   nullable=True)

    # 상태: pending → confirmed / cancelled
    status = db.Column(db.String(20), default='pending', index=True)

    linked_makeup_request_id = db.Column(db.String(36), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    student = db.relationship('Student', backref='absence_notices')
    course = db.relationship('Course', backref='absence_notices')
    creator = db.relationship('User', foreign_keys=[created_by])
    admin_confirmer = db.relationship('User', foreign_keys=[admin_confirmed_by])

    def __repr__(self):
        return f'<AbsenceNotice {self.notice_id} - {self.student_id} - {self.absence_date}>'

    @property
    def notice_type_label(self):
        return '결석' if self.notice_type == 'absent' else '지각'

    @property
    def status_label(self):
        labels = {'pending': '미확인', 'confirmed': '확인완료', 'cancelled': '취소'}
        return labels.get(self.status, self.status)

    @property
    def needs_teacher_confirm(self):
        """관리자가 입력 → 강사 확인 필요"""
        return self.created_by_role == 'admin' and not self.teacher_confirmed

    @property
    def needs_admin_confirm(self):
        """강사가 입력 → 관리자 확인 필요"""
        return self.created_by_role == 'teacher' and not self.admin_confirmed
