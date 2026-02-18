# -*- coding: utf-8 -*-
"""문자 메시지 모델"""
from datetime import datetime
import uuid
from app.models import db


class Message(db.Model):
    """문자 메시지 (SMS/LMS)"""
    __tablename__ = 'messages'

    message_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 발신자 (관리자/강사)
    sender_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')

    # 메시지 유형
    message_type = db.Column(db.String(10), nullable=False)  # 'SMS', 'LMS'

    # 제목 (LMS만)
    subject = db.Column(db.String(200), nullable=True)

    # 내용
    content = db.Column(db.Text, nullable=False)

    # 수신자 유형
    recipient_type = db.Column(db.String(20), nullable=False)  # 'individual', 'group', 'all'

    # 수신자 정보 (JSON 형식으로 저장)
    # individual: [{"student_id": "...", "name": "...", "phone": "..."}]
    # group: [{"student_id": "...", "name": "...", "phone": "..."}, ...]
    # all: "all_students" or "all_parents"
    recipients_json = db.Column(db.Text, nullable=False)

    # 발송 통계
    total_recipients = db.Column(db.Integer, default=0)  # 총 발송 대상
    success_count = db.Column(db.Integer, default=0)     # 성공
    failed_count = db.Column(db.Integer, default=0)      # 실패

    # 발송 상태
    status = db.Column(db.String(20), default='pending')  # 'pending', 'sending', 'completed', 'failed'

    # 예약 발송
    is_scheduled = db.Column(db.Boolean, default=False)
    scheduled_at = db.Column(db.DateTime, nullable=True)

    # 발송 시간
    sent_at = db.Column(db.DateTime, nullable=True)

    # 메모
    notes = db.Column(db.Text, nullable=True)

    # 메타데이터
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Message {self.message_id}: {self.message_type} to {self.total_recipients} recipients>'

    @property
    def is_sent(self):
        """발송 완료 여부"""
        return self.status == 'completed'

    @property
    def success_rate(self):
        """발송 성공률"""
        if self.total_recipients == 0:
            return 0
        return (self.success_count / self.total_recipients) * 100

    @property
    def content_length(self):
        """내용 길이 (바이트)"""
        return len(self.content.encode('utf-8'))

    @property
    def char_count(self):
        """글자 수"""
        return len(self.content)


class MessageRecipient(db.Model):
    """문자 수신자 상세 (개별 발송 결과 추적)"""
    __tablename__ = 'message_recipients'

    recipient_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 메시지
    message_id = db.Column(db.String(36), db.ForeignKey('messages.message_id'), nullable=False)
    message = db.relationship('Message', backref='recipients')

    # 수신자 정보
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id'), nullable=True)
    student = db.relationship('Student', backref='received_messages')

    # 수신자 연락처
    recipient_name = db.Column(db.String(100), nullable=False)
    recipient_phone = db.Column(db.String(20), nullable=False)

    # 발송 결과
    status = db.Column(db.String(20), default='pending')  # 'pending', 'sent', 'failed'
    sent_at = db.Column(db.DateTime, nullable=True)

    # 실패 사유
    error_message = db.Column(db.Text, nullable=True)

    # 메타데이터
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MessageRecipient {self.recipient_id}: {self.recipient_name} - {self.status}>'
