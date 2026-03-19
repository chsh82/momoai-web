# -*- coding: utf-8 -*-
"""처리 대기 업무(Action Item) 모델"""
from datetime import datetime, date
from app.models import db


class ActionItem(db.Model):
    __tablename__ = 'action_items'

    item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default='기타')   # 상담처리/민원/결제/행정/기타
    priority = db.Column(db.String(20), default='medium') # high/medium/low
    status = db.Column(db.String(20), default='pending')  # pending/in_progress/completed

    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    assigned_to = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='SET NULL'), nullable=True)

    due_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by], backref='created_action_items')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_action_items')
    student = db.relationship('Student', foreign_keys=[student_id], backref='action_items')

    CATEGORIES = ['상담처리', '민원', '결제', '행정', '기타']

    PRIORITY_LABELS = {'high': '높음', 'medium': '보통', 'low': '낮음'}
    PRIORITY_COLORS = {'high': 'red', 'medium': 'yellow', 'low': 'green'}
    PRIORITY_ICONS  = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}

    STATUS_LABELS = {'pending': '대기중', 'in_progress': '처리중', 'completed': '완료'}
    STATUS_COLORS = {'pending': 'gray', 'in_progress': 'blue', 'completed': 'green'}

    @property
    def priority_label(self):
        return self.PRIORITY_LABELS.get(self.priority, self.priority)

    @property
    def priority_icon(self):
        return self.PRIORITY_ICONS.get(self.priority, '')

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def is_overdue(self):
        """마감일이 지났고 아직 완료 안 된 항목"""
        if self.due_date and self.status != 'completed':
            return self.due_date < date.today()
        return False

    def complete(self):
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
