# -*- coding: utf-8 -*-
"""ClassBoard 모델 - 수업별 학생 게시판"""
from datetime import datetime
import uuid
from app.models import db


class ClassBoardPost(db.Model):
    """클래스 게시판 게시글"""
    __tablename__ = 'class_board_posts'

    post_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                         nullable=True, index=True)

    # 게시글 내용
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 게시글 유형
    post_type = db.Column(db.String(20), default='question')  # question, notice, material, discussion

    # 표시 옵션
    is_pinned = db.Column(db.Boolean, default=False)  # 상단 고정 (강사만 가능)
    is_notice = db.Column(db.Boolean, default=False)  # 공지사항 (강사만 가능)

    # 통계
    view_count = db.Column(db.Integer, default=0)
    comment_count = db.Column(db.Integer, default=0)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', backref=db.backref('board_posts', passive_deletes=True))
    author = db.relationship('User', backref='class_board_posts')
    comments = db.relationship('ClassBoardComment', back_populates='post',
                              cascade='all, delete-orphan', order_by='ClassBoardComment.created_at')

    def __repr__(self):
        return f'<ClassBoardPost {self.post_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(ClassBoardPost, self).__init__(**kwargs)
        if not self.post_id:
            self.post_id = str(uuid.uuid4())

    def can_edit(self, user):
        """사용자가 수정할 수 있는지 확인"""
        # 본인이거나 관리자
        return self.author_id == user.user_id or user.role in ['admin', 'manager']

    def can_delete(self, user):
        """사용자가 삭제할 수 있는지 확인"""
        # 본인이거나 관리자, 또는 해당 수업의 강사
        if self.author_id == user.user_id or user.role in ['admin', 'manager']:
            return True
        if self.course.teacher_id == user.user_id:
            return True
        return False


class ClassBoardComment(db.Model):
    """클래스 게시판 댓글"""
    __tablename__ = 'class_board_comments'

    comment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(db.String(36), db.ForeignKey('class_board_posts.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                         nullable=True, index=True)

    # 댓글 내용
    content = db.Column(db.Text, nullable=False)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    post = db.relationship('ClassBoardPost', back_populates='comments')
    author = db.relationship('User', backref='class_board_comments')

    def __repr__(self):
        return f'<ClassBoardComment {self.comment_id}>'

    def __init__(self, **kwargs):
        super(ClassBoardComment, self).__init__(**kwargs)
        if not self.comment_id:
            self.comment_id = str(uuid.uuid4())

    def can_edit(self, user):
        """사용자가 수정할 수 있는지 확인"""
        # 본인이거나 관리자
        return self.author_id == user.user_id or user.role in ['admin', 'manager']

    def can_delete(self, user):
        """사용자가 삭제할 수 있는지 확인"""
        # 본인이거나 관리자, 또는 해당 수업의 강사
        if self.author_id == user.user_id or user.role in ['admin', 'manager']:
            return True
        if self.post.course.teacher_id == user.user_id:
            return True
        return False
