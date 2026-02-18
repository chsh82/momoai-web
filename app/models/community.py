# -*- coding: utf-8 -*-
"""커뮤니티 관련 모델"""
from datetime import datetime
from app.models import db


class Post(db.Model):
    """게시글 모델"""
    __tablename__ = 'posts'

    post_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    # category: notice(공지), question(질문), free(자유), resource(자료)
    views = db.Column(db.Integer, default=0)
    likes_count = db.Column(db.Integer, default=0)
    is_pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='posts')
    comments = db.relationship('Comment', back_populates='post',
                              cascade='all, delete-orphan',
                              order_by='Comment.created_at')
    likes = db.relationship('PostLike', back_populates='post',
                           cascade='all, delete-orphan')
    post_tags = db.relationship('PostTag', back_populates='post',
                               cascade='all, delete-orphan')
    bookmarks = db.relationship('Bookmark', back_populates='post',
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Post {self.post_id} - {self.title}>'

    def __init__(self, **kwargs):
        super(Post, self).__init__(**kwargs)
        if not self.post_id:
            import uuid
            self.post_id = str(uuid.uuid4())

    @property
    def comment_count(self):
        """댓글 수 (대댓글 포함)"""
        return len(self.comments)

    def is_liked_by(self, user_id):
        """특정 사용자가 좋아요를 눌렀는지 확인"""
        return any(like.user_id == user_id for like in self.likes)

    def is_bookmarked_by(self, user_id):
        """특정 사용자가 북마크했는지 확인"""
        return any(bookmark.user_id == user_id for bookmark in self.bookmarks)

    @property
    def tags(self):
        """게시글의 태그 목록"""
        from app.models.tag import Tag
        return [pt.tag for pt in self.post_tags]


class Comment(db.Model):
    """댓글 모델"""
    __tablename__ = 'comments'

    comment_id = db.Column(db.String(36), primary_key=True)
    post_id = db.Column(db.String(36), db.ForeignKey('posts.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    parent_comment_id = db.Column(db.String(36),
                                  db.ForeignKey('comments.comment_id', ondelete='CASCADE'),
                                  nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    post = db.relationship('Post', back_populates='comments')
    user = db.relationship('User', backref='comments')
    parent = db.relationship('Comment', remote_side=[comment_id], backref='replies')

    def __repr__(self):
        return f'<Comment {self.comment_id}>'

    def __init__(self, **kwargs):
        super(Comment, self).__init__(**kwargs)
        if not self.comment_id:
            import uuid
            self.comment_id = str(uuid.uuid4())

    @property
    def is_reply(self):
        """대댓글 여부"""
        return self.parent_comment_id is not None

    @property
    def reply_count(self):
        """대댓글 수"""
        return len(self.replies) if hasattr(self, 'replies') else 0


class PostLike(db.Model):
    """게시글 좋아요 모델"""
    __tablename__ = 'post_likes'

    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       primary_key=True)
    post_id = db.Column(db.String(36), db.ForeignKey('posts.post_id', ondelete='CASCADE'),
                       primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='post_likes')
    post = db.relationship('Post', back_populates='likes')

    def __repr__(self):
        return f'<PostLike {self.user_id} - {self.post_id}>'
