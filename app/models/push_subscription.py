# -*- coding: utf-8 -*-
"""Push Subscription 모델 — Web Push 알림 구독 정보 저장"""
from datetime import datetime
from app.models import db


class PushSubscription(db.Model):
    """사용자 Push 구독 정보"""
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='push_subscriptions')

    def __repr__(self):
        return f'<PushSubscription user={self.user_id}>'
