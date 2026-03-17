# -*- coding: utf-8 -*-
"""SessionAdjustment 모델 (이월/무료수업 조정)"""
from datetime import datetime
import uuid
from app.models import db


class SessionAdjustment(db.Model):
    """이월/무료수업 조정 모델

    발생 경로:
    - teacher_excused: 강사가 출결 화면에서 '인정결석' 클릭 → type=NULL, status=pending_review
    - admin_manual: 관리자가 직접 입력 → type 즉시 지정, status=pending

    처리 흐름:
    pending_review → (관리자 분류) → pending → (결제 반영) → applied
                                              → (취소) → cancelled
    """
    __tablename__ = 'session_adjustments'

    adjustment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 대상
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                           nullable=False, index=True)
    enrollment_id = db.Column(db.String(36), db.ForeignKey('course_enrollments.enrollment_id', ondelete='CASCADE'),
                              nullable=False, index=True)

    # 출결 연동 (강사 인정결석 시)
    attendance_id = db.Column(db.String(36), db.ForeignKey('attendance.attendance_id', ondelete='SET NULL'),
                              nullable=True)

    # 조정 유형
    # NULL: 강사 인정결석 후 관리자 분류 전
    # 'rollover': 이월 (다음 결제 기간으로 회차 이월)
    # 'free_session': 무료수업 (체험/시범 등)
    adjustment_type = db.Column(db.String(20), nullable=True, index=True)

    # 회차 수 (1~4, 관리자 직접 입력 시 최대 4회)
    sessions_count = db.Column(db.Integer, nullable=False, default=1)

    # 사유
    reason = db.Column(db.Text, nullable=True)

    # 발생 경로
    source = db.Column(db.String(20), nullable=False)
    # 'teacher_excused': 강사 인정결석
    # 'admin_manual': 관리자 직접 입력

    # 처리 상태
    status = db.Column(db.String(20), nullable=False, default='pending_review', index=True)
    # 'pending_review': 강사 인정결석 후 관리자 분류 대기
    # 'pending': 분류 완료, 다음 결제 반영 대기
    # 'applied': 결제에 반영 완료
    # 'cancelled': 취소

    # 결제 반영 정보
    applied_payment_id = db.Column(db.String(36), db.ForeignKey('payments.payment_id', ondelete='SET NULL'),
                                   nullable=True)

    # 관리자 검토 정보
    reviewed_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                            nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # 강사 알림 (관리자 직접 입력 시)
    notified_teacher_at = db.Column(db.DateTime, nullable=True)

    # 등록자
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                           nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student = db.relationship('Student', foreign_keys=[student_id], backref='session_adjustments')
    enrollment = db.relationship('CourseEnrollment', foreign_keys=[enrollment_id],
                                 backref='session_adjustments')
    attendance = db.relationship('Attendance', foreign_keys=[attendance_id],
                                 backref='session_adjustment')
    applied_payment = db.relationship('Payment', foreign_keys=[applied_payment_id],
                                      backref='applied_adjustments')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<SessionAdjustment {self.adjustment_id}: {self.adjustment_type} x{self.sessions_count}>'

    def __init__(self, **kwargs):
        super(SessionAdjustment, self).__init__(**kwargs)
        if not self.adjustment_id:
            self.adjustment_id = str(uuid.uuid4())

    @property
    def type_label(self):
        """유형 한글 표시"""
        if self.adjustment_type == 'rollover':
            return '이월'
        elif self.adjustment_type == 'free_session':
            return '무료수업'
        return '미분류'

    @property
    def status_label(self):
        """상태 한글 표시"""
        labels = {
            'pending_review': '분류 대기',
            'pending': '적용 대기',
            'applied': '적용 완료',
            'cancelled': '취소'
        }
        return labels.get(self.status, self.status)

    @property
    def source_label(self):
        """발생 경로 한글 표시"""
        if self.source == 'teacher_excused':
            return '강사 인정결석'
        elif self.source == 'admin_manual':
            return '관리자 입력'
        return self.source

    @classmethod
    def get_pending_for_enrollment(cls, enrollment_id):
        """특정 enrollment의 미적용 조정 건 전체 조회"""
        return cls.query.filter_by(
            enrollment_id=enrollment_id,
            status='pending'
        ).all()

    @classmethod
    def get_pending_before(cls, enrollment_id, before_date):
        """선불 청구용: 특정 날짜 이전에 발생한 미적용 조정 건만 조회

        Args:
            enrollment_id: 수강 ID
            before_date: 기준일 (결제 기간 시작일). 이 날짜 이전 발생 건만 포함.
        """
        from datetime import datetime
        cutoff = datetime(before_date.year, before_date.month, before_date.day)
        return cls.query.filter(
            cls.enrollment_id == enrollment_id,
            cls.status == 'pending',
            cls.created_at < cutoff
        ).all()

    @classmethod
    def get_pending_count(cls, enrollment_id):
        """미적용 총 회차 수 반환"""
        adjustments = cls.get_pending_for_enrollment(enrollment_id)
        return sum(a.sessions_count for a in adjustments)

    @classmethod
    def get_pending_review_count(cls):
        """전체 분류 대기 건수 (관리자 대시보드용)"""
        return cls.query.filter_by(status='pending_review').count()
