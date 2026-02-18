"""Video models for educational content management."""

import uuid
from datetime import datetime
from app.models import db


class Video(db.Model):
    """Educational videos (YouTube links) for students."""
    __tablename__ = 'videos'

    video_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    grade = db.Column(db.String(20), nullable=False, index=True)  # 초1-고3
    youtube_url = db.Column(db.String(500), nullable=False)
    youtube_video_id = db.Column(db.String(50), nullable=True)  # Extracted for embed
    publish_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    is_public = db.Column(db.Boolean, default=True, nullable=False, index=True)
    target_audience = db.Column(db.Text, nullable=False)  # JSON: {"type": "grade"|"course", "grades": [...], "course_ids": [...]}
    view_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)

    # Relationships
    creator = db.relationship('User', backref='created_videos')
    views = db.relationship('VideoView', backref='video', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Video {self.title}>'


class VideoView(db.Model):
    """Track video views."""
    __tablename__ = 'video_views'

    view_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = db.Column(db.String(36), db.ForeignKey('videos.video_id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'), nullable=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref='user_video_views')
    student = db.relationship('Student', backref='student_video_views')

    def __repr__(self):
        return f'<VideoView {self.view_id}>'
