# -*- coding: utf-8 -*-
"""보강수업 신청 모델"""
from datetime import datetime
import uuid
from app.models import db


class MakeupClassRequest(db.Model):
    """보강수업 신청 모델"""
    __tablename__ = 'makeup_class_requests'

    request_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    requested_course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                                   nullable=False, index=True)
    original_course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='SET NULL'),
                                  nullable=True)  # 원래 수강 중인 수업 (선택사항)

    # 신청 사유
    reason = db.Column(db.Text, nullable=True)

    # 상태
    status = db.Column(db.String(20), default='pending', index=True)  # pending, approved, rejected

    # 신청 정보
    request_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    requested_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))  # 신청자 (학생 또는 학부모)

    # 관리자 응답
    admin_response_date = db.Column(db.DateTime, nullable=True)
    admin_response_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))
    admin_notes = db.Column(db.Text, nullable=True)  # 관리자 메모/거절 사유

    # 승인 시 생성된 보강 수업 정보
    created_makeup_course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='SET NULL'),
                                        nullable=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='makeup_requests')
    requested_course = db.relationship('Course', foreign_keys=[requested_course_id])
    original_course = db.relationship('Course', foreign_keys=[original_course_id])
    created_makeup_course = db.relationship('Course', foreign_keys=[created_makeup_course_id])
    requester = db.relationship('User', foreign_keys=[requested_by])
    admin_responder = db.relationship('User', foreign_keys=[admin_response_by])

    def __repr__(self):
        return f'<MakeupClassRequest {self.request_id}: {self.student_id} -> {self.requested_course_id}>'

    def __init__(self, **kwargs):
        super(MakeupClassRequest, self).__init__(**kwargs)
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
