# -*- coding: utf-8 -*-
"""사이트 콘텐츠 모델 (모모 소식)"""
from datetime import datetime
from app.models import db


class SiteContent(db.Model):
    __tablename__ = 'site_contents'

    key = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.String(36), db.ForeignKey('users.user_id'))

    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
