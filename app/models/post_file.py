# -*- coding: utf-8 -*-
"""게시글 파일 첨부 모델"""
from datetime import datetime
from pathlib import Path
from app.models import db


class PostFile(db.Model):
    """게시글 파일 첨부 모델"""
    __tablename__ = 'post_files'

    file_id = db.Column(db.String(36), primary_key=True)
    post_id = db.Column(db.String(36), db.ForeignKey('posts.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)  # 원본 파일명
    stored_filename = db.Column(db.String(255), nullable=False)  # 저장된 파일명 (고유)
    file_size = db.Column(db.Integer, nullable=False)  # 바이트 단위
    file_type = db.Column(db.String(100), nullable=True)  # MIME type
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    post = db.relationship('Post', backref='files')

    def __repr__(self):
        return f'<PostFile {self.filename}>'

    def __init__(self, **kwargs):
        super(PostFile, self).__init__(**kwargs)
        if not self.file_id:
            import uuid
            self.file_id = str(uuid.uuid4())

    @property
    def file_size_str(self):
        """파일 크기를 읽기 쉬운 형태로 변환"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    @property
    def is_image(self):
        """이미지 파일 여부"""
        if not self.file_type:
            return False
        return self.file_type.startswith('image/')

    @property
    def extension(self):
        """파일 확장자"""
        return Path(self.filename).suffix.lower()
