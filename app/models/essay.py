# -*- coding: utf-8 -*-
"""Essay 관련 모델"""
from datetime import datetime
from app.models import db


class Essay(db.Model):
    """첨삭 작업 모델"""
    __tablename__ = 'essays'

    essay_id = db.Column(db.String(36), primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    title = db.Column(db.String(255), nullable=True)
    original_text = db.Column(db.Text, nullable=False)
    grade = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='draft', index=True)
    # status: draft, processing, reviewing, completed, failed
    current_version = db.Column(db.Integer, default=1)
    is_finalized = db.Column(db.Boolean, default=False)
    finalized_at = db.Column(db.DateTime, nullable=True)

    # 파일 첨부 (이미지, 워드 등)
    attachment_filename = db.Column(db.String(255), nullable=True)  # 원본 파일명
    attachment_path = db.Column(db.String(500), nullable=True)  # 저장 경로

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    student = db.relationship('Student', back_populates='essays')
    user = db.relationship('User', back_populates='essays')
    versions = db.relationship('EssayVersion', back_populates='essay',
                              cascade='all, delete-orphan',
                              order_by='EssayVersion.version_number')
    result = db.relationship('EssayResult', back_populates='essay',
                            uselist=False, cascade='all, delete-orphan')
    scores = db.relationship('EssayScore', back_populates='essay',
                            cascade='all, delete-orphan')
    notes = db.relationship('EssayNote', back_populates='essay',
                           cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Essay {self.essay_id} - {self.student.name if self.student else "Unknown"}>'

    def __init__(self, **kwargs):
        super(Essay, self).__init__(**kwargs)
        if not self.essay_id:
            import uuid
            self.essay_id = str(uuid.uuid4())

    @property
    def is_completed(self):
        """완료 여부"""
        return self.status == 'completed'

    @property
    def is_processing(self):
        """처리 중 여부"""
        return self.status == 'processing'

    @property
    def latest_version(self):
        """최신 버전"""
        if self.versions:
            return self.versions[-1]
        return None


class EssayVersion(db.Model):
    """첨삭 버전 관리 모델"""
    __tablename__ = 'essay_versions'

    version_id = db.Column(db.String(36), primary_key=True)
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    html_path = db.Column(db.String(500), nullable=True)
    revision_note = db.Column(db.Text, nullable=True)  # 수정 요청 내용
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    essay = db.relationship('Essay', back_populates='versions')

    __table_args__ = (
        db.UniqueConstraint('essay_id', 'version_number', name='uq_essay_version'),
    )

    def __repr__(self):
        return f'<EssayVersion {self.essay_id} v{self.version_number}>'

    def __init__(self, **kwargs):
        super(EssayVersion, self).__init__(**kwargs)
        if not self.version_id:
            import uuid
            self.version_id = str(uuid.uuid4())


class EssayResult(db.Model):
    """첨삭 결과 모델"""
    __tablename__ = 'essay_results'

    result_id = db.Column(db.String(36), primary_key=True)
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    version_id = db.Column(db.String(36), db.ForeignKey('essay_versions.version_id', ondelete='CASCADE'),
                          nullable=False, index=True)
    html_path = db.Column(db.String(500), nullable=True)
    pdf_path = db.Column(db.String(500), nullable=True)
    total_score = db.Column(db.Numeric(4, 1), nullable=True)
    final_grade = db.Column(db.String(10), nullable=True)
    ai_detection_score = db.Column(db.Integer, nullable=True)
    plagiarism_score = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    essay = db.relationship('Essay', back_populates='result')
    version = db.relationship('EssayVersion')

    def __repr__(self):
        return f'<EssayResult {self.essay_id}>'

    def __init__(self, **kwargs):
        super(EssayResult, self).__init__(**kwargs)
        if not self.result_id:
            import uuid
            self.result_id = str(uuid.uuid4())
