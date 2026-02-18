"""Teaching Material models for educational content management."""

import uuid
from datetime import datetime
from app.models import db


class TeachingMaterial(db.Model):
    """Teaching materials/resources for students."""
    __tablename__ = 'teaching_materials'

    material_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    grade = db.Column(db.String(20), nullable=False, index=True)  # 초1-고3
    original_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # bytes
    file_type = db.Column(db.String(50), nullable=False)  # pdf, doc, etc.
    publish_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    is_public = db.Column(db.Boolean, default=True, nullable=False, index=True)
    target_audience = db.Column(db.Text, nullable=False)  # JSON: {"type": "grade"|"course", "grades": [...], "course_ids": [...]}
    download_count = db.Column(db.Integer, default=0, nullable=False)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)

    # Relationships
    creator = db.relationship('User', backref='created_teaching_materials')
    downloads = db.relationship('TeachingMaterialDownload', backref='teaching_material', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<TeachingMaterial {self.title}>'


class TeachingMaterialDownload(db.Model):
    """Track material downloads."""
    __tablename__ = 'teaching_material_downloads'

    download_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    material_id = db.Column(db.String(36), db.ForeignKey('teaching_materials.material_id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'), nullable=True)
    downloaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref='teaching_material_downloads')
    student = db.relationship('Student', backref='teaching_material_downloads')

    def __repr__(self):
        return f'<Download {self.download_id}>'
