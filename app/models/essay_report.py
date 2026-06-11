# -*- coding: utf-8 -*-
"""모모아이 분기 리포트 모델"""
import json
import uuid
from datetime import datetime
from app.models import db


class EssayReport(db.Model):
    __tablename__ = 'essay_reports'

    report_id = db.Column(db.String(36), primary_key=True,
                          default=lambda: str(uuid.uuid4()))

    student_id = db.Column(db.Integer, db.ForeignKey('students.student_id'),
                           nullable=False, index=True)
    period_id = db.Column(db.String(36), db.ForeignKey('payment_periods.period_id'),
                          nullable=False, index=True)

    # 주 첨삭 모델 ('standard', 'harkness', 'elementary')
    correction_model = db.Column(db.String(20))

    # 상태: draft → reviewing → published
    status = db.Column(db.String(20), default='draft', index=True)

    # 집계된 통계 (JSON)
    stats_json = db.Column(db.Text)

    # 첨삭 패턴 (JSON list)
    format_patterns_json = db.Column(db.Text)   # 형식첨삭 반복 패턴
    content_patterns_json = db.Column(db.Text)  # 내용첨삭 반복 패턴

    # AI 자동 총평
    ai_summary = db.Column(db.Text)

    # 강사 수동 총평 (별도 추가)
    teacher_comment = db.Column(db.Text)

    # 검수 정보
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    reviewed_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='essay_reports')
    period = db.relationship('PaymentPeriod', backref='essay_reports')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.report_id:
            self.report_id = str(uuid.uuid4())

    @property
    def stats(self):
        return json.loads(self.stats_json) if self.stats_json else {}

    @property
    def format_patterns(self):
        return json.loads(self.format_patterns_json) if self.format_patterns_json else []

    @property
    def content_patterns(self):
        return json.loads(self.content_patterns_json) if self.content_patterns_json else []

    @property
    def status_label(self):
        return {'draft': '초안', 'reviewing': '검수중', 'published': '발행됨'}.get(self.status, self.status)
