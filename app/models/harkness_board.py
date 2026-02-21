# -*- coding: utf-8 -*-
"""하크니스 게시판 모델"""
from datetime import datetime
import uuid
from app.models import db


class HarknessBoard(db.Model):
    """하크니스 게시판"""
    __tablename__ = 'harkness_boards'

    board_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 게시판 유형
    board_type = db.Column(db.String(20), nullable=False, index=True)  # 'course', 'harkness_all'

    # 연결된 수업 (course_type일 경우)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=True, index=True)

    # 게시판 정보
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # 생성자 (관리자 또는 강사)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    # 게시글 양식 ('harkness': 3질문 양식, 'general': 일반 양식)
    post_format = db.Column(db.String(20), default='harkness')

    # 활성화 여부
    is_active = db.Column(db.Boolean, default=True, index=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', backref='harkness_boards')
    creator = db.relationship('User', foreign_keys=[created_by])
    posts = db.relationship('HarknessPost',
                           back_populates='board',
                           cascade='all, delete-orphan',
                           lazy='dynamic',
                           order_by='desc(HarknessPost.created_at)')

    def __repr__(self):
        return f'<HarknessBoard {self.board_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(HarknessBoard, self).__init__(**kwargs)
        if not self.board_id:
            self.board_id = str(uuid.uuid4())

    @property
    def post_count(self):
        """게시글 수"""
        return self.posts.count()

    @property
    def latest_post(self):
        """최신 게시글"""
        return self.posts.first()


class HarknessPost(db.Model):
    """하크니스 게시글"""
    __tablename__ = 'harkness_posts'

    post_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    board_id = db.Column(db.String(36), db.ForeignKey('harkness_boards.board_id', ondelete='CASCADE'),
                        nullable=False, index=True)

    # 작성자
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)

    # 게시글 정보
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)  # 자유 형식 내용 (선택)

    # 하크니스 질문 템플릿 (3개 질문)
    question1 = db.Column(db.Text, nullable=True)
    question1_intent = db.Column(db.Text, nullable=True)
    question2 = db.Column(db.Text, nullable=True)
    question2_intent = db.Column(db.Text, nullable=True)
    question3 = db.Column(db.Text, nullable=True)
    question3_intent = db.Column(db.Text, nullable=True)

    # 조회수
    view_count = db.Column(db.Integer, default=0)

    # 공지사항 여부 (강사/관리자만)
    is_notice = db.Column(db.Boolean, default=False, index=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    board = db.relationship('HarknessBoard', back_populates='posts')
    author = db.relationship('User', backref='harkness_posts')
    comments = db.relationship('HarknessComment',
                              back_populates='post',
                              cascade='all, delete-orphan',
                              lazy='dynamic',
                              order_by='HarknessComment.created_at')
    likes = db.relationship('HarknessPostLike',
                           back_populates='post',
                           cascade='all, delete-orphan',
                           lazy='dynamic')

    def __repr__(self):
        return f'<HarknessPost {self.post_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(HarknessPost, self).__init__(**kwargs)
        if not self.post_id:
            self.post_id = str(uuid.uuid4())

    @property
    def comment_count(self):
        """댓글 수"""
        return self.comments.count()

    @property
    def like_count(self):
        """좋아요 수"""
        return self.likes.count()

    def is_liked_by(self, user_id):
        """특정 사용자가 좋아요를 눌렀는지 확인"""
        return self.likes.filter_by(user_id=user_id).first() is not None


class HarknessComment(db.Model):
    """하크니스 댓글"""
    __tablename__ = 'harkness_comments'

    comment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(db.String(36), db.ForeignKey('harkness_posts.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)

    # 작성자
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                         nullable=False, index=True)

    # 대댓글 (부모 댓글)
    parent_comment_id = db.Column(db.String(36), db.ForeignKey('harkness_comments.comment_id', ondelete='CASCADE'),
                                  nullable=True, index=True)

    # 댓글 내용
    content = db.Column(db.Text, nullable=False)

    # 특정 질문에 달린 댓글인 경우 (1, 2, 3 / null=게시글 전체 댓글)
    question_number = db.Column(db.Integer, nullable=True, index=True)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    post = db.relationship('HarknessPost', back_populates='comments')
    author = db.relationship('User', backref='harkness_comments')

    # 대댓글 관계 (self-referential)
    replies = db.relationship('HarknessComment',
                             backref=db.backref('parent', remote_side=[comment_id]),
                             lazy='dynamic',
                             cascade='all, delete-orphan')

    def __repr__(self):
        return f'<HarknessComment {self.comment_id}>'

    def __init__(self, **kwargs):
        super(HarknessComment, self).__init__(**kwargs)
        if not self.comment_id:
            self.comment_id = str(uuid.uuid4())

    @property
    def reply_count(self):
        """답글 수"""
        return self.replies.count()


class HarknessPostLike(db.Model):
    """하크니스 게시글 좋아요"""
    __tablename__ = 'harkness_post_likes'

    like_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(db.String(36), db.ForeignKey('harkness_posts.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    post = db.relationship('HarknessPost', back_populates='likes')
    user = db.relationship('User', backref='harkness_likes')

    # Unique constraint: 한 사용자가 같은 게시글에 한 번만 좋아요 가능
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='unique_post_user_like'),
    )

    def __repr__(self):
        return f'<HarknessPostLike {self.like_id}>'

    def __init__(self, **kwargs):
        super(HarknessPostLike, self).__init__(**kwargs)
        if not self.like_id:
            self.like_id = str(uuid.uuid4())


class HarknessQuestionLike(db.Model):
    """하크니스 질문별 좋아요"""
    __tablename__ = 'harkness_question_likes'

    like_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(db.String(36), db.ForeignKey('harkness_posts.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    question_number = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    post = db.relationship('HarknessPost', backref='question_likes')
    user = db.relationship('User', backref='harkness_question_likes')

    __table_args__ = (
        db.UniqueConstraint('post_id', 'question_number', 'user_id', name='unique_question_user_like'),
    )

    def __repr__(self):
        return f'<HarknessQuestionLike post={self.post_id} q={self.question_number}>'

    def __init__(self, **kwargs):
        super(HarknessQuestionLike, self).__init__(**kwargs)
        if not self.like_id:
            self.like_id = str(uuid.uuid4())
