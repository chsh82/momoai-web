# -*- coding: utf-8 -*-
"""게시판 공통 이미지 첨부 모델"""
from datetime import datetime
import uuid
from app.models import db


class PostImage(db.Model):
    """게시판 공통 이미지 첨부 모델

    board_type 값:
    - 'community'    : 커뮤니티 게시판
    - 'teacher_board': 강사 게시판 (TeacherBoardAttachment과 병행)
    - 'harkness'     : 하크니스 게시판
    - 'class_board'  : 수업 게시판
    - 'inquiry'      : 문의 게시판
    - 'hall_of_fame' : 명예의 전당
    - 'admission_info': 입시 정보
    """
    __tablename__ = 'post_images'

    image_id = db.Column(db.String(36), primary_key=True,
                         default=lambda: str(uuid.uuid4()))
    board_type = db.Column(db.String(50), nullable=False, index=True)
    post_id = db.Column(db.String(36), nullable=False, index=True)  # FK 없음 (다형성)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    order = db.Column(db.Integer, default=0)  # 표시 순서 (0~9)
    uploaded_by = db.Column(db.String(36),
                            db.ForeignKey('users.user_id', ondelete='SET NULL'),
                            nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def __repr__(self):
        return f'<PostImage {self.image_id}: {self.original_filename}>'

    def __init__(self, **kwargs):
        super(PostImage, self).__init__(**kwargs)
        if not self.image_id:
            self.image_id = str(uuid.uuid4())

    @property
    def url(self):
        """이미지 URL"""
        from flask import url_for
        return url_for('community.serve_post_image', filename=self.stored_filename)

    @property
    def file_size_str(self):
        """파일 크기를 읽기 쉬운 형태로 변환"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
