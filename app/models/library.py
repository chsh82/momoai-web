# -*- coding: utf-8 -*-
"""도서 자료실 모델"""
from datetime import datetime
import uuid
from app.models import db


class HallOfFame(db.Model):
    """명예의 전당 - 우수 답안 및 수상작"""
    __tablename__ = 'hall_of_fame'

    post_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 게시글 정보
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 분류
    category = db.Column(db.String(50), nullable=False, index=True)  # 'excellent_answer', 'mock_exam_award', 'essay_award', 'other'

    # 학생 정보 (선택)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='SET NULL'), nullable=True)
    student_name = db.Column(db.String(100), nullable=True)  # 익명 처리용
    grade = db.Column(db.String(20), nullable=True)  # 학년

    # 연결된 첨삭 글(선택) - "우수답안 선정" 버튼과 명예의 전당이 같은 글을
    # 가리키는지 판단하는 기준. 이 값이 있으면 EX01 마일리지 중복 지급을
    # 여기로 막는다(2026-09-17 결정, app/essays/routes.py select_excellent
    # / app/library/routes.py create_hall_of_fame 참고).
    essay_id = db.Column(db.String(36), db.ForeignKey('essays.essay_id', ondelete='SET NULL'),
                        nullable=True, index=True)

    # 수상 정보
    award_name = db.Column(db.String(200), nullable=True)  # 수상명
    award_date = db.Column(db.Date, nullable=True)  # 수상일

    # 수업 정보 (선택)
    week_number = db.Column(db.Integer, nullable=True)  # 주차
    book_id = db.Column(db.String(36), db.ForeignKey('books.book_id', ondelete='SET NULL'),
                       nullable=True, index=True)  # 수업도서

    # 파일 첨부
    file_path = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)

    # 조회수
    view_count = db.Column(db.Integer, default=0)

    # 공개 여부
    is_published = db.Column(db.Boolean, default=True, index=True)

    # 메타 정보
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='hall_of_fame_posts')
    creator = db.relationship('User', backref='hall_of_fame_posts')
    book = db.relationship('Book')
    essay = db.relationship('Essay', backref='hall_of_fame_posts')

    def __repr__(self):
        return f'<HallOfFame {self.post_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(HallOfFame, self).__init__(**kwargs)
        if not self.post_id:
            self.post_id = str(uuid.uuid4())

    @property
    def like_count(self):
        return len(self.likes)

    def liked_by(self, user_id):
        if not user_id:
            return False
        return any(like.user_id == user_id for like in self.likes)


class HallOfFameComment(db.Model):
    """명예의 전당 댓글 - 간단한 칭찬·격려 코멘트용(대댓글 없음)"""
    __tablename__ = 'hall_of_fame_comments'

    comment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(db.String(36), db.ForeignKey('hall_of_fame.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    content = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    post = db.relationship('HallOfFame', backref=db.backref(
        'comments', cascade='all, delete-orphan', order_by='HallOfFameComment.created_at'))
    user = db.relationship('User')

    def __repr__(self):
        return f'<HallOfFameComment {self.comment_id}: post={self.post_id}>'

    def __init__(self, **kwargs):
        super(HallOfFameComment, self).__init__(**kwargs)
        if not self.comment_id:
            self.comment_id = str(uuid.uuid4())


class HallOfFameLike(db.Model):
    """명예의 전당 좋아요 - 사용자 1명당 게시글 1개에 1회만"""
    __tablename__ = 'hall_of_fame_likes'

    like_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = db.Column(db.String(36), db.ForeignKey('hall_of_fame.post_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'),
                       nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='uq_hall_of_fame_like_post_user'),
    )

    post = db.relationship('HallOfFame', backref=db.backref('likes', cascade='all, delete-orphan'))
    user = db.relationship('User')

    def __repr__(self):
        return f'<HallOfFameLike post={self.post_id} user={self.user_id}>'

    def __init__(self, **kwargs):
        super(HallOfFameLike, self).__init__(**kwargs)
        if not self.like_id:
            self.like_id = str(uuid.uuid4())


class AdmissionInfo(db.Model):
    """입시정보 게시판"""
    __tablename__ = 'admission_info'

    post_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 게시글 정보
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    # 분류
    category = db.Column(db.String(50), nullable=False, index=True)  # 'university', 'high_school', 'policy', 'schedule', 'tips', 'other'

    # 대상 학년
    target_grades = db.Column(db.Text, nullable=True)  # JSON: ['초등', '중등', '고등']

    # 외부 링크
    external_url = db.Column(db.String(500), nullable=True)

    # 파일 첨부
    file_path = db.Column(db.String(500), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)

    # 조회수
    view_count = db.Column(db.Integer, default=0)

    # 중요 공지 여부
    is_important = db.Column(db.Boolean, default=False, index=True)

    # 공개 기간
    publish_date = db.Column(db.Date, nullable=True, index=True)
    expire_date = db.Column(db.Date, nullable=True, index=True)

    # 메타 정보
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', backref='admission_info_posts')

    def __repr__(self):
        return f'<AdmissionInfo {self.post_id}: {self.title}>'

    def __init__(self, **kwargs):
        super(AdmissionInfo, self).__init__(**kwargs)
        if not self.post_id:
            self.post_id = str(uuid.uuid4())

    def is_active(self):
        """현재 공개 기간인지 확인"""
        if not self.publish_date:
            return True
        today = datetime.now().date()
        if self.expire_date:
            return self.publish_date <= today <= self.expire_date
        return self.publish_date <= today
