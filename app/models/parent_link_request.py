# -*- coding: utf-8 -*-
"""학부모-자녀 연결 요청 모델"""
from datetime import datetime
import uuid
from app.models import db


class ParentLinkRequest(db.Model):
    """학부모가 자녀 연결을 요청하는 모델"""
    __tablename__ = 'parent_link_requests'

    request_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)

    # 학부모가 입력한 자녀 정보
    student_name = db.Column(db.String(100), nullable=False)
    student_birth_date = db.Column(db.Date, nullable=True)
    student_grade = db.Column(db.String(20), nullable=True)  # 초1, 중2, 고3 등
    student_school = db.Column(db.String(200), nullable=True)
    relation_type = db.Column(db.String(20), default='parent')  # parent, father, mother, guardian
    additional_info = db.Column(db.Text, nullable=True)  # 추가 정보

    # 관리자가 매칭한 학생
    matched_student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='SET NULL'),
                                   nullable=True, index=True)

    # 상태 관리
    status = db.Column(db.String(20), default='pending', index=True)
    # pending: 관리자 검토 대기
    # approved: 승인됨 (연결 완료)
    # rejected: 거절됨
    # cancelled: 학부모가 취소

    # 관리자 응답
    reviewed_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)  # 관리자 메모 (거절 사유 등)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent = db.relationship('User', foreign_keys=[parent_id], backref='link_requests')
    matched_student = db.relationship('Student', backref='link_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<ParentLinkRequest {self.request_id}: {self.parent_id} -> {self.student_name}>'

    def __init__(self, **kwargs):
        super(ParentLinkRequest, self).__init__(**kwargs)
        if not self.request_id:
            self.request_id = str(uuid.uuid4())
