# -*- coding: utf-8 -*-
"""마일리지·뱃지 모델

근거 문서: docs/mileage/05_DB설계서.md, docs/mileage/01_마일리지_운영정책.md
"""
from datetime import datetime
from app.models import db


class PointEvent(db.Model):
    """포인트 원장 - 적립·취소를 한 줄씩 기록한다. 잔액 컬럼은 두지 않고 합계로 계산한다."""
    __tablename__ = 'point_events'
    __table_args__ = (
        db.UniqueConstraint('student_id', 'activity_code', 'source_type', 'source_id', 'entry_type',
                           name='uq_point_event_source'),
        db.Index('ix_point_event_student_season', 'student_id', 'season'),
        db.Index('ix_point_event_season_status', 'season', 'status'),
        db.Index('ix_point_event_source', 'source_type', 'source_id'),
    )

    event_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False)
    activity_code = db.Column(db.String(10), nullable=False)  # RW01, QZ01, CM01 등
    entry_type = db.Column(db.String(10), nullable=False)  # award(적립) / cancel(취소)
    points = db.Column(db.Integer, nullable=False)  # 적립은 양수, 취소는 음수
    status = db.Column(db.String(10), nullable=False, default='pending')  # pending / confirmed / cancelled
    source_type = db.Column(db.String(30), nullable=False)
    # essay, post, comment, quiz_session, attendance_week, attendance_quarter, manual
    source_id = db.Column(db.String(64), nullable=False)  # 대상 레코드 ID (문자열로 통일 저장)
    season = db.Column(db.String(7), nullable=False)  # '2026-09' (KST 기준)
    occurred_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # 활동 발생 시각(UTC)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancel_reason = db.Column(db.String(200), nullable=True)
    related_event_id = db.Column(db.Integer, db.ForeignKey('point_events.event_id'), nullable=True)
    # 취소 기록이 가리키는 원본 적립 기록
    granted_by = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=True)  # 수동 지급자
    memo = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='point_events')
    granter = db.relationship('User', foreign_keys=[granted_by])
    related_event = db.relationship('PointEvent', remote_side=[event_id], backref='cancel_events')

    def __repr__(self):
        return f'<PointEvent {self.student_id} {self.activity_code} {self.entry_type} {self.points}>'


class Badge(db.Model):
    """뱃지 정의 - 조건을 데이터로 관리해 코드 수정 없이 추가할 수 있게 한다."""
    __tablename__ = 'badges'

    badge_code = db.Column(db.String(10), primary_key=True)  # BG01 ~ BG10
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(10), nullable=False)  # 초급 / 중급 / 고급 / 최종
    icon_path = db.Column(db.String(200), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_repeatable = db.Column(db.Boolean, nullable=False, default=False)
    rule_type = db.Column(db.String(30), nullable=False)
    # first_event, count_threshold, external_metric, manual, all_badges
    rule_config = db.Column(db.Text, nullable=True)  # JSON
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f'<Badge {self.badge_code} {self.name}>'


class StudentBadge(db.Model):
    """뱃지 획득 이력"""
    __tablename__ = 'student_badges'
    __table_args__ = (
        db.UniqueConstraint('student_id', 'badge_code', name='uq_student_badge'),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False)
    badge_code = db.Column(db.String(10), db.ForeignKey('badges.badge_code'), nullable=False)
    earned_count = db.Column(db.Integer, nullable=False, default=1)  # 반복 획득 횟수
    first_earned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_earned_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    granted_by = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=True)  # 수동 수여자
    revoked_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    student = db.relationship('Student', backref='student_badges')
    badge = db.relationship('Badge')
    granter = db.relationship('User', foreign_keys=[granted_by])

    def __repr__(self):
        return f'<StudentBadge {self.student_id} {self.badge_code} x{self.earned_count}>'


class MonthlyRanking(db.Model):
    """월간 랭킹 확정 스냅샷 - 실시간 계산이 아니라 확정 시점에 저장한다."""
    __tablename__ = 'monthly_rankings'
    __table_args__ = (
        db.UniqueConstraint('season', 'level_group', 'student_id', name='uq_monthly_ranking'),
    )

    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.String(7), nullable=False)  # 2026-09
    level_group = db.Column(db.String(20), nullable=False)  # 학년 또는 레벨 구분값
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    points = db.Column(db.Integer, nullable=False)  # 확정 시즌 점수
    is_final = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', backref='monthly_rankings')

    def __repr__(self):
        return f'<MonthlyRanking {self.season} {self.level_group} #{self.rank} {self.student_id}>'


class MileageConsent(db.Model):
    """공개 동의 이력 - 항목별로 따로 저장하고, 변경 시 새 행을 추가한다."""
    __tablename__ = 'mileage_consents'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False)
    consent_type = db.Column(db.String(1), nullable=False)  # A(랭킹 공개) / B(앱 내 게시) / C(홍보물 활용)
    is_agreed = db.Column(db.Boolean, nullable=False)
    agreed_by_user_id = db.Column(db.String(36), db.ForeignKey('users.user_id'), nullable=False)
    agreed_by_relation = db.Column(db.String(10), nullable=False)  # self / parent
    doc_version = db.Column(db.String(10), nullable=False)
    agreed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    student = db.relationship('Student', backref='mileage_consents')
    agreed_by = db.relationship('User', foreign_keys=[agreed_by_user_id])

    def __repr__(self):
        return f'<MileageConsent {self.student_id} {self.consent_type} {self.is_agreed}>'
