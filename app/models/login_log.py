# -*- coding: utf-8 -*-
"""로그인 시도 로그 모델"""
from datetime import datetime
from app.models import db


class LoginAttemptLog(db.Model):
    """로그인 시도 기록"""
    __tablename__ = 'login_attempt_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False)  # IPv6 최대 45자
    user_agent = db.Column(db.String(500), nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False)
    failure_reason = db.Column(db.String(100), nullable=True)  # wrong_password, account_locked 등
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        status = 'SUCCESS' if self.success else 'FAILED'
        return f'<LoginAttemptLog {self.email} {status} at {self.attempted_at}>'
