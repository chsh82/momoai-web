# -*- coding: utf-8 -*-
"""강사 프롬프트 템플릿 모델"""
from datetime import datetime
from app.models import db


class TeacherPromptTemplate(db.Model):
    """강사가 저장해두는 재사용 프롬프트 템플릿"""
    __tablename__ = 'teacher_prompt_templates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    teacher_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship('User', foreign_keys=[teacher_id])

    def __repr__(self):
        return f'<TeacherPromptTemplate {self.id} - {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'created_at': self.created_at.strftime('%Y-%m-%d'),
        }
