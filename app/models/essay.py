# -*- coding: utf-8 -*-
"""Essay 관련 모델"""
from datetime import datetime
from app.models import db

# 과제 유형(essay_type) 값과 표시명. 새 유형이 늘어나도 이 딕셔너리만
# 고치면 되게 하드코딩을 피한다(2026-08-29 결정사항 - 마일리지 RW01/RW02
# 분기, BG01/BG03 뱃지 조건이 이 값을 그대로 참조한다).
ESSAY_TYPES = {
    'basic': '기본과제글',
    'rewriting': '리라이팅',
    'etc': '기타',
}
ESSAY_TYPE_DEFAULT = 'basic'


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
    essay_type = db.Column(db.String(20), nullable=False, default=ESSAY_TYPE_DEFAULT)
    # essay_type: basic(기본과제글) / rewriting(리라이팅) / etc(기타) - ESSAY_TYPES 참고.
    # 첨삭 확정(is_finalized) 전까지만 변경 가능 - 확정 후 변경을 허용하면 포인트
    # 취소 후 다른 코드로 재지급해야 하는데, source_id(essay_id) 유니크 제약 때문에
    # 재지급이 막혀 점수가 0이 되는 문제가 생긴다(2026-08-29 결정사항).
    status = db.Column(db.String(20), nullable=False, default='draft', index=True)

    # 수업-세션 연결 (자동 배정 또는 수동 설정)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='SET NULL'),
                         nullable=True, index=True)
    session_id = db.Column(db.String(36), db.ForeignKey('course_sessions.session_id', ondelete='SET NULL'),
                          nullable=True, index=True)
    session_assigned_auto = db.Column(db.Boolean, default=True, nullable=False)
    # 첨삭 모델: standard(스탠다드) / harkness(하크니스)
    correction_model = db.Column(db.String(20), nullable=False, default='standard')
    # AI API 제공자: claude / gemini
    api_provider = db.Column(db.String(20), nullable=False, default='claude')
    # 강사 사전 가이드 (첨삭 프롬프트에 포함됨)
    teacher_guide = db.Column(db.Text, nullable=True)

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
    course = db.relationship('Course', foreign_keys=[course_id])
    session = db.relationship('CourseSession', foreign_keys=[session_id])
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


class CorrectionAttachment(db.Model):
    """강사 수동 첨삭 첨부파일"""
    __tablename__ = 'correction_attachments'

    attachment_id = db.Column(db.String(36), primary_key=True)
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    version_id = db.Column(db.String(36), db.ForeignKey('essay_versions.version_id', ondelete='CASCADE'),
                           nullable=True, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)  # 'image' or 'pdf'
    file_size = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    essay = db.relationship('Essay', backref=db.backref('correction_attachments',
                                                         cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<CorrectionAttachment {self.original_filename}>'

    def __init__(self, **kwargs):
        super(CorrectionAttachment, self).__init__(**kwargs)
        if not self.attachment_id:
            import uuid
            self.attachment_id = str(uuid.uuid4())
