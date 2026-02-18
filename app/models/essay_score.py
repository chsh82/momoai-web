# -*- coding: utf-8 -*-
"""Essay Score 및 Note 모델"""
from datetime import datetime
from app.models import db


class EssayScore(db.Model):
    """첨삭 점수 모델 (18개 지표)"""
    __tablename__ = 'essay_scores'

    score_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    version_id = db.Column(db.String(36), db.ForeignKey('essay_versions.version_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    category = db.Column(db.String(20), nullable=False)  # 사고유형, 통합지표
    indicator_name = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Numeric(3, 1), nullable=False)  # 0.0 ~ 10.0

    # Relationships
    essay = db.relationship('Essay', back_populates='scores')
    version = db.relationship('EssayVersion')

    def __repr__(self):
        return f'<EssayScore {self.indicator_name}: {self.score}>'

    __table_args__ = (
        db.CheckConstraint('score >= 0 AND score <= 10', name='check_score_range'),
    )


class EssayNote(db.Model):
    """첨삭 주의사항/참고사항 모델"""
    __tablename__ = 'essay_notes'

    note_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    note_type = db.Column(db.String(20), nullable=True)  # 주의사항, 참고사항
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    essay = db.relationship('Essay', back_populates='notes')

    def __repr__(self):
        return f'<EssayNote {self.note_type}: {self.content[:30]}...>'
