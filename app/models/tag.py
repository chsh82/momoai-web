# -*- coding: utf-8 -*-
"""태그 모델"""
from datetime import datetime
from app.models import db


class Tag(db.Model):
    """태그 모델"""
    __tablename__ = 'tags'

    tag_id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    posts = db.relationship('PostTag', back_populates='tag', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Tag {self.name}>'

    def __init__(self, **kwargs):
        super(Tag, self).__init__(**kwargs)
        if not self.tag_id:
            import uuid
            self.tag_id = str(uuid.uuid4())

    @property
    def post_count(self):
        """이 태그를 사용한 게시글 수"""
        return len(self.posts)


class PostTag(db.Model):
    """게시글-태그 연결 테이블"""
    __tablename__ = 'post_tags'

    post_id = db.Column(db.String(36), db.ForeignKey('posts.post_id', ondelete='CASCADE'),
                       primary_key=True)
    tag_id = db.Column(db.String(36), db.ForeignKey('tags.tag_id', ondelete='CASCADE'),
                      primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    post = db.relationship('Post', back_populates='post_tags')
    tag = db.relationship('Tag', back_populates='posts')

    def __repr__(self):
        return f'<PostTag {self.post_id} - {self.tag_id}>'


class Bookmark(db.Model):
    """북마크 모델"""
    __tablename__ = 'bookmarks'

    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       primary_key=True)
    post_id = db.Column(db.String(36), db.ForeignKey('posts.post_id', ondelete='CASCADE'),
                       primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref='bookmarks')
    post = db.relationship('Post', back_populates='bookmarks')

    def __repr__(self):
        return f'<Bookmark {self.user_id} - {self.post_id}>'
