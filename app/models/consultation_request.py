# -*- coding: utf-8 -*-
"""상담 신청 모델.

학부모가 관리자에게 접수하는 구조다(강사 직접 승인 없음). 관리자가 접수를
책임지고, 필요하면 강사와 내부 협의(기존 강사↔관리자 메신저 재사용)를
거친 뒤 학부모와의 일정을 확정한다. 강사 회신(내부 협의)과 일정 확정(학부모
응답)은 서로 다른 행동이라 상태 컬럼을 하나만 두고 internal_conversation_id로
내부 협의 스레드만 연결한다 - 학부모용 대화 스레드는 1차 범위에 없어 컬럼을
아직 추가하지 않는다(추후 필요 시 마이그레이션으로 추가).
"""
import uuid
from datetime import datetime

from app.models import db

CATEGORY_CHOICES = ['신규상담', '퇴원상담', '분기별상담', '진로진학상담', '기타']

# pending(접수대기) -> scheduled(일정확정)/rejected(거절) -> completed(상담기록 연결)
STATUS_CHOICES = ['pending', 'scheduled', 'rejected', 'completed']


class ConsultationRequest(db.Model):
    """상담 신청 - 학부모 접수 -> 관리자 처리 -> 상담 기록 연결."""
    __tablename__ = 'consultation_requests'

    request_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    requester_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                             nullable=True, index=True)  # 신청한 학부모

    category = db.Column(db.String(50), nullable=False)
    preferred_date = db.Column(db.Date, nullable=True)
    preferred_note = db.Column(db.String(200), nullable=True)
    reason = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), default='pending', index=True)

    reject_reason = db.Column(db.Text, nullable=True)
    scheduled_date = db.Column(db.Date, nullable=True)
    scheduled_note = db.Column(db.String(200), nullable=True)

    responded_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    # 관리자<->강사 내부 협의 (기존 messages 모듈의 Conversation 재사용, 학부모는 접근 불가)
    internal_conversation_id = db.Column(db.Integer,
                                         db.ForeignKey('conversations.conversation_id', ondelete='SET NULL'),
                                         nullable=True)

    # 완료 후 실제 상담 기록과 연결
    consultation_id = db.Column(db.Integer,
                                db.ForeignKey('consultation_records.consultation_id', ondelete='SET NULL'),
                                nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship('Student', foreign_keys=[student_id])
    requester = db.relationship('User', foreign_keys=[requester_id])
    responder = db.relationship('User', foreign_keys=[responded_by])
    internal_conversation = db.relationship('Conversation', foreign_keys=[internal_conversation_id])
    consultation_record = db.relationship('ConsultationRecord', foreign_keys=[consultation_id])

    def __repr__(self):
        return f'<ConsultationRequest {self.request_id}: {self.status}>'
