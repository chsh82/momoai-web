# -*- coding: utf-8 -*-
"""강사↔관리자 1:1 대화 스레드 모델"""
from datetime import datetime
from app.models import db


class Conversation(db.Model):
    """대화 스레드 — 두 사용자 간의 1:1 대화"""
    __tablename__ = 'conversations'

    conversation_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 두 참여자 (항상 teacher↔admin 조합)
    user1_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    user2_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user1 = db.relationship('User', foreign_keys=[user1_id], backref='conversations_as_user1')
    user2 = db.relationship('User', foreign_keys=[user2_id], backref='conversations_as_user2')
    messages = db.relationship('ConversationMessage', backref='conversation',
                                lazy='dynamic', order_by='ConversationMessage.created_at')

    def get_other_user(self, current_user_id):
        """상대방 User 객체 반환"""
        if self.user1_id == current_user_id:
            return self.user2
        return self.user1

    def unread_count_for(self, user_id):
        """특정 사용자의 미읽은 메시지 수 (상대방이 보낸 미읽은 메시지)"""
        return ConversationMessage.query.filter(
            ConversationMessage.conversation_id == self.conversation_id,
            ConversationMessage.sender_id != user_id,
            ConversationMessage.is_read == False
        ).count()

    def __repr__(self):
        return f'<Conversation {self.conversation_id}: {self.user1_id} ↔ {self.user2_id}>'


class ConversationMessage(db.Model):
    """대화 스레드 내 개별 메시지"""
    __tablename__ = 'conversation_messages'

    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.conversation_id',
                                                           ondelete='CASCADE'),
                                nullable=False, index=True)
    sender_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    attachment_url = db.Column(db.String(500), nullable=True)
    attachment_name = db.Column(db.String(200), nullable=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id])

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()

    def __repr__(self):
        return f'<ConversationMessage {self.message_id}>'
