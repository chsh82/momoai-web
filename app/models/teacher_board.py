# -*- coding: utf-8 -*-
"""강사 게시판 모델"""
from datetime import datetime
import uuid
from app.models import db


class TeacherBoard(db.Model):
    """강사 게시판"""
    __tablename__ = 'teacher_boards'

    board_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 작성자
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)

    # 게시글 정보
    title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)  # HTML 지원

    # 조회수
    view_count = db.Column(db.Integer, default=0)

    # 공지사항 여부 (관리자만)
    is_notice = db.Column(db.Boolean, default=False, index=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship('User', backref='teacher_boards')
    attachments = db.relationship('TeacherBoardAttachment',
                                 back_populates='board',
                                 cascade='all, delete-orphan',
                                 lazy='dynamic')

    def __repr__(self):
        return f'<TeacherBoard {self.board_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(TeacherBoard, self).__init__(**kwargs)
        if not self.board_id:
            self.board_id = str(uuid.uuid4())

    @property
    def attachment_count(self):
        """첨부파일 개수"""
        return self.attachments.count()

    @property
    def image_attachments(self):
        """이미지 첨부파일만"""
        return self.attachments.filter(
            TeacherBoardAttachment.file_type.in_(['jpg', 'jpeg', 'png', 'gif', 'webp'])
        ).all()

    @property
    def file_attachments(self):
        """일반 파일 첨부만"""
        return self.attachments.filter(
            ~TeacherBoardAttachment.file_type.in_(['jpg', 'jpeg', 'png', 'gif', 'webp'])
        ).all()


class TeacherBoardAttachment(db.Model):
    """강사 게시판 첨부파일"""
    __tablename__ = 'teacher_board_attachments'

    attachment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    board_id = db.Column(db.String(36), db.ForeignKey('teacher_boards.board_id', ondelete='CASCADE'),
                        nullable=False, index=True)

    # 파일 정보
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)  # UUID 기반
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    file_type = db.Column(db.String(50), nullable=False)  # 확장자

    # 이미지 여부
    is_image = db.Column(db.Boolean, default=False)

    # 업로드 정보
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.String(36), db.ForeignKey('users.user_id'))

    # Relationships
    board = db.relationship('TeacherBoard', back_populates='attachments')
    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    def __repr__(self):
        return f'<TeacherBoardAttachment {self.original_filename}>'

    def __init__(self, **kwargs):
        super(TeacherBoardAttachment, self).__init__(**kwargs)
        if not self.attachment_id:
            self.attachment_id = str(uuid.uuid4())
