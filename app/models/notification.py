# -*- coding: utf-8 -*-
"""알림 모델"""
from datetime import datetime
from app.models import db


class Notification(db.Model):
    """알림 모델"""
    __tablename__ = 'notifications'

    notification_id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    notification_type = db.Column(db.String(50), nullable=False, index=True)
    # notification_type: comment(댓글), like(좋아요), essay_complete(첨삭완료), mention(멘션)

    title = db.Column(db.String(500), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link_url = db.Column(db.String(500), nullable=True)  # 클릭 시 이동할 URL

    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)

    # 알림 관련 엔티티 정보 (선택적)
    related_user_id = db.Column(db.String(36), nullable=True)  # 알림을 발생시킨 사용자
    related_entity_type = db.Column(db.String(50), nullable=True)  # post, comment, essay 등
    related_entity_id = db.Column(db.String(36), nullable=True)  # 관련 엔티티 ID

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = db.relationship('User', backref='notifications')

    def __repr__(self):
        return f'<Notification {self.notification_id} - {self.notification_type}>'

    def __init__(self, **kwargs):
        super(Notification, self).__init__(**kwargs)
        if not self.notification_id:
            import uuid
            self.notification_id = str(uuid.uuid4())

    def mark_as_read(self):
        """알림을 읽음으로 표시"""
        self.is_read = True
        self.read_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def create_notification(user_id, notification_type, title, message,
                          link_url=None, related_user_id=None,
                          related_entity_type=None, related_entity_id=None):
        """알림 생성 헬퍼 메서드"""
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            link_url=link_url,
            related_user_id=related_user_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @staticmethod
    def get_unread_count(user_id):
        """읽지 않은 알림 수"""
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def mark_all_as_read(user_id):
        """모든 알림을 읽음으로 표시"""
        notifications = Notification.query.filter_by(user_id=user_id, is_read=False).all()
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
        db.session.commit()
