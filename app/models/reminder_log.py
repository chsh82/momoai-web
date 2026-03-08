# -*- coding: utf-8 -*-
"""수업 리마인더 발송 이력 (중복 발송 방지)"""
from app.models import db
from datetime import datetime


class ReminderLog(db.Model):
    __tablename__ = 'reminder_logs'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('course_sessions.session_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('session_id', name='uq_reminder_session'),
    )
