# -*- coding: utf-8 -*-
"""과제/공지 답글 모델"""
from datetime import datetime
import uuid
from app.models import db


class NotificationReply(db.Model):
    """과제/공지 알림에 대한 학생↔강사 답글"""
    __tablename__ = 'notification_replies'

    reply_id = db.Column(db.String(36), primary_key=True,
                         default=lambda: str(uuid.uuid4()))
    notification_id = db.Column(db.String(36),
                                db.ForeignKey('notifications.notification_id', ondelete='CASCADE'),
                                nullable=False, index=True)
    author_id = db.Column(db.String(36),
                          db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    notification = db.relationship('Notification', backref='replies')
    author = db.relationship('User', backref='notification_replies')

    def __repr__(self):
        return f'<NotificationReply {self.reply_id}>'

    def __init__(self, **kwargs):
        super(NotificationReply, self).__init__(**kwargs)
        if not self.reply_id:
            self.reply_id = str(uuid.uuid4())
