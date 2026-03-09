# -*- coding: utf-8 -*-
"""학생 주의사항 경고 모델"""
from datetime import datetime
from app.models import db

CATEGORY_LABELS = {
    'consultation_note': '상담 유의사항',
    'parent_request':    '학부모 요구사항',
    'behavior':          '행동 특이사항',
    'other':             '기타',
}

SEVERITY_META = {
    'caution': {'label': '주의', 'color': 'yellow'},
    'warning': {'label': '경고', 'color': 'orange'},
    'danger':  {'label': '위험', 'color': 'red'},
}


class StudentCaution(db.Model):
    """학생 주의사항/경고 이력"""
    __tablename__ = 'student_cautions'

    caution_id      = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id      = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                                nullable=False, index=True)
    author_id       = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                                nullable=True)

    # 분류
    category        = db.Column(db.String(30), nullable=False, default='other')
    severity        = db.Column(db.String(20), nullable=False, default='caution')  # caution / warning / danger

    # 내용
    title           = db.Column(db.String(200), nullable=False)
    content         = db.Column(db.Text, nullable=False)

    # 해결 처리
    is_resolved     = db.Column(db.Boolean, default=False, nullable=False, index=True)
    resolved_by_id  = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                                nullable=True)
    resolved_at     = db.Column(db.DateTime, nullable=True)
    resolve_note    = db.Column(db.Text, nullable=True)

    # 연결된 상담 기록 (옵션)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultation_records.consultation_id',
                                                           ondelete='SET NULL'), nullable=True)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    student         = db.relationship('Student', foreign_keys=[student_id],
                                      backref=db.backref('cautions', lazy='dynamic'))
    author          = db.relationship('User', foreign_keys=[author_id])
    resolved_by     = db.relationship('User', foreign_keys=[resolved_by_id])
    consultation    = db.relationship('ConsultationRecord', foreign_keys=[consultation_id],
                                      backref=db.backref('cautions', lazy='dynamic'))

    @property
    def category_label(self):
        return CATEGORY_LABELS.get(self.category, self.category)

    @property
    def severity_label(self):
        return SEVERITY_META.get(self.severity, {}).get('label', self.severity)

    @property
    def severity_color(self):
        return SEVERITY_META.get(self.severity, {}).get('color', 'gray')

    def resolve(self, resolver_id, note=''):
        self.is_resolved    = True
        self.resolved_by_id = resolver_id
        self.resolved_at    = datetime.utcnow()
        self.resolve_note   = note

    def __repr__(self):
        return f'<StudentCaution {self.caution_id}: {self.student_id} [{self.severity}]>'
