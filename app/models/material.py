# -*- coding: utf-8 -*-
"""학습 자료 모델"""
from datetime import datetime
import uuid
from app.models import db


class Material(db.Model):
    """학습 자료 모델"""
    __tablename__ = 'materials'

    material_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 기본 정보
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # 파일 정보
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # bytes
    file_type = db.Column(db.String(50), nullable=False)  # pdf, docx, pptx, etc

    # 분류
    category = db.Column(db.String(50), default='general')  # textbook, reference, example, past_exam, etc
    tags = db.Column(db.String(200), nullable=True)  # 콤마로 구분된 태그

    # 연결 정보
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=True, index=True)
    uploaded_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                           nullable=False, index=True)

    # 접근 제어
    access_level = db.Column(db.String(20), default='all')  # all, course, tier
    tier_restriction = db.Column(db.String(100), nullable=True)  # A,B,C,VIP

    # 통계
    download_count = db.Column(db.Integer, default=0)

    # 상태
    is_published = db.Column(db.Boolean, default=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', backref='materials')
    uploader = db.relationship('User', backref='uploaded_materials')
    downloads = db.relationship('MaterialDownload', back_populates='material',
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Material {self.material_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(Material, self).__init__(**kwargs)
        if not self.material_id:
            self.material_id = str(uuid.uuid4())

    @property
    def file_size_mb(self):
        """파일 크기 (MB)"""
        return round(self.file_size / (1024 * 1024), 2)

    @property
    def tier_list(self):
        """티어 리스트"""
        if not self.tier_restriction:
            return []
        return [t.strip() for t in self.tier_restriction.split(',')]

    def can_access(self, user, student=None):
        """사용자가 접근 가능한지 확인"""
        # 관리자/강사는 항상 접근 가능
        if user.role in ['admin', 'teacher']:
            return True

        # 전체 공개
        if self.access_level == 'all':
            return True

        # 수업별 제한
        if self.access_level == 'course' and self.course_id:
            if student:
                # 학생이 해당 수업을 듣는지 확인
                from app.models import CourseEnrollment
                enrollment = CourseEnrollment.query.filter_by(
                    student_id=student.student_id,
                    course_id=self.course_id,
                    status='active'
                ).first()
                if enrollment:
                    return True

        # 티어별 제한
        if self.access_level == 'tier' and self.tier_restriction:
            if student and student.tier in self.tier_list:
                return True

        return False


class MaterialDownload(db.Model):
    """자료 다운로드 기록"""
    __tablename__ = 'material_downloads'

    download_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    material_id = db.Column(db.String(36), db.ForeignKey('materials.material_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=True, index=True)

    downloaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    material = db.relationship('Material', back_populates='downloads')
    user = db.relationship('User', backref='material_downloads')
    student = db.relationship('Student', backref='material_downloads')

    def __repr__(self):
        return f'<MaterialDownload {self.download_id}>'

    def __init__(self, **kwargs):
        super(MaterialDownload, self).__init__(**kwargs)
        if not self.download_id:
            self.download_id = str(uuid.uuid4())
