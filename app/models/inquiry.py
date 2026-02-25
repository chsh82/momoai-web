# -*- coding: utf-8 -*-
"""문의 게시판 모델"""
import uuid
from datetime import datetime
from app.models import db


class InquiryPost(db.Model):
    __tablename__ = 'inquiry_posts'

    inquiry_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, answered
    is_private = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # 수신자 (None=관리자 전체, teacher user_id=특정 강사)
    recipient_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=True)

    author = db.relationship('User', foreign_keys=[author_id])
    recipient = db.relationship('User', foreign_keys=[recipient_id])
    replies = db.relationship('InquiryReply', back_populates='inquiry',
                               cascade='all, delete-orphan', order_by='InquiryReply.created_at')


class InquiryReply(db.Model):
    __tablename__ = 'inquiry_replies'

    reply_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inquiry_id = db.Column(db.String(36), db.ForeignKey('inquiry_posts.inquiry_id'), nullable=False)
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[author_id])
    inquiry = db.relationship('InquiryPost', back_populates='replies')
