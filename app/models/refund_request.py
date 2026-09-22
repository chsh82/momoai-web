# -*- coding: utf-8 -*-
"""환불 요청 모델.

학부모가 결제 건에 대해 환불을 요청하면 자동으로 처리하지 않고 관리자에게
알림만 보낸다. 실제 환불 여부/거절은 관리자가 직접 검토 후 응답해야 한다.
승인 시 Payment.status를 'refunded'로 바꾸는 것도 관리자의 명시적 액션이며,
결제대행사(토스) API를 자동으로 호출하지 않는다 - 실제 송금/취소는 관리자가
이 시스템 밖에서 처리한 뒤 승인 버튼을 누르는 것을 전제로 한다.
"""
import uuid
from datetime import datetime

from app.models import db

STATUS_CHOICES = ['pending', 'approved', 'rejected']


class RefundRequest(db.Model):
    """환불 요청 - 학부모 접수 -> 관리자 검토 후 승인/거절."""
    __tablename__ = 'refund_requests'

    request_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    payment_id = db.Column(db.String(36), db.ForeignKey('payments.payment_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    requester_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                             nullable=True, index=True)

    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)

    admin_notes = db.Column(db.Text, nullable=True)
    responded_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payment = db.relationship('Payment', foreign_keys=[payment_id], backref='refund_requests')
    requester = db.relationship('User', foreign_keys=[requester_id])
    responder = db.relationship('User', foreign_keys=[responded_by])

    def __repr__(self):
        return f'<RefundRequest {self.request_id}: {self.status}>'
