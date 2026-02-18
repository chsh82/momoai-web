# -*- coding: utf-8 -*-
"""Announcement 모델"""
from datetime import datetime
import uuid
from app.models import db


class Announcement(db.Model):
    """학원 전체 공지사항 모델"""
    __tablename__ = 'announcements'

    announcement_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    author_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                         nullable=True, index=True)

    # 제목 및 내용
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 공지 유형
    announcement_type = db.Column(db.String(20), default='general')  # general, urgent, event, system

    # 대상 역할 (JSON 배열로 저장, 예: ['student', 'parent', 'teacher'])
    target_roles = db.Column(db.Text, nullable=True)  # 'all' 또는 'student,parent,teacher'

    # 대상 티어 (특정 등급 학생만, 예: 'A,B')
    target_tiers = db.Column(db.String(100), nullable=True)

    # 표시 옵션
    is_pinned = db.Column(db.Boolean, default=False)  # 상단 고정
    is_popup = db.Column(db.Boolean, default=False)  # 로그인시 팝업
    is_published = db.Column(db.Boolean, default=True)  # 게시 여부

    # 게시 기간
    publish_start = db.Column(db.DateTime, nullable=True)
    publish_end = db.Column(db.DateTime, nullable=True)

    # 통계
    view_count = db.Column(db.Integer, default=0)

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author = db.relationship('User', backref='announcements')
    reads = db.relationship('AnnouncementRead', back_populates='announcement',
                           cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Announcement {self.announcement_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(Announcement, self).__init__(**kwargs)
        if not self.announcement_id:
            self.announcement_id = str(uuid.uuid4())

    @property
    def is_active(self):
        """현재 활성 상태 여부"""
        if not self.is_published:
            return False
        now = datetime.utcnow()
        if self.publish_start and now < self.publish_start:
            return False
        if self.publish_end and now > self.publish_end:
            return False
        return True

    @property
    def target_roles_list(self):
        """대상 역할 리스트"""
        if not self.target_roles or self.target_roles == 'all':
            return ['all']
        return [r.strip() for r in self.target_roles.split(',')]

    @property
    def target_tiers_list(self):
        """대상 티어 리스트"""
        if not self.target_tiers:
            return []
        return [t.strip() for t in self.target_tiers.split(',')]

    def is_visible_to_user(self, user):
        """특정 사용자가 볼 수 있는지 확인"""
        if not self.is_active:
            return False

        target_roles = self.target_roles_list
        if 'all' not in target_roles and user.role not in target_roles:
            return False

        # 티어 제한이 있는 경우 (학생만 해당)
        if self.target_tiers and user.role == 'student':
            # student.tier를 확인해야 함 (User와 Student 관계 필요)
            pass

        return True

    def mark_as_read_by(self, user_id):
        """사용자가 읽음 처리"""
        existing = AnnouncementRead.query.filter_by(
            announcement_id=self.announcement_id,
            user_id=user_id
        ).first()

        if not existing:
            read_record = AnnouncementRead(
                announcement_id=self.announcement_id,
                user_id=user_id
            )
            db.session.add(read_record)
            self.view_count += 1

    def is_read_by(self, user_id):
        """사용자가 읽었는지 확인"""
        return AnnouncementRead.query.filter_by(
            announcement_id=self.announcement_id,
            user_id=user_id
        ).first() is not None


class AnnouncementRead(db.Model):
    """공지사항 읽음 기록"""
    __tablename__ = 'announcement_reads'

    read_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    announcement_id = db.Column(db.String(36), db.ForeignKey('announcements.announcement_id', ondelete='CASCADE'),
                               nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)

    read_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    announcement = db.relationship('Announcement', back_populates='reads')
    user = db.relationship('User', backref='announcement_reads')

    def __repr__(self):
        return f'<AnnouncementRead {self.user_id} read {self.announcement_id}>'

    def __init__(self, **kwargs):
        super(AnnouncementRead, self).__init__(**kwargs)
        if not self.read_id:
            self.read_id = str(uuid.uuid4())

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('announcement_id', 'user_id', name='unique_announcement_read'),
    )
