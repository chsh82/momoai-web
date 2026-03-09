# -*- coding: utf-8 -*-
"""Payment 모델"""
from datetime import datetime
import uuid
from app.models import db


class Payment(db.Model):
    """결제 모델"""
    __tablename__ = 'payments'

    payment_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    enrollment_id = db.Column(db.String(36), db.ForeignKey('course_enrollments.enrollment_id', ondelete='CASCADE'),
                             nullable=False, index=True)
    course_id = db.Column(db.String(36), db.ForeignKey('courses.course_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    student_id = db.Column(db.String(36), db.ForeignKey('students.student_id', ondelete='CASCADE'),
                          nullable=False, index=True)

    # 결제 금액
    amount = db.Column(db.Integer, nullable=False)  # 최종 결제 금액 (할인 적용 후)
    original_amount = db.Column(db.Integer, nullable=True)  # 할인 전 원금액

    # 할인 정보
    discount_type = db.Column(db.String(50), nullable=True)  # acquaintance, sibling, quarterly, none
    discount_rate = db.Column(db.Float, default=0.0)  # 할인율 (0.0 ~ 1.0)
    discount_amount = db.Column(db.Integer, default=0)  # 할인 금액

    # 결제 유형
    payment_type = db.Column(db.String(20), default='tuition')  # tuition, registration, material, etc
    payment_period = db.Column(db.String(20), nullable=True)  # monthly, quarterly

    # 출석 기반 결제 정보
    sessions_covered = db.Column(db.Integer, default=0)  # 이 결제로 커버되는 세션 수
    from_session = db.Column(db.Integer, nullable=True)  # 시작 회차
    to_session = db.Column(db.Integer, nullable=True)  # 종료 회차

    # 결제 기간 정보
    period_id = db.Column(db.String(36), db.ForeignKey('payment_periods.period_id', ondelete='SET NULL'),
                          nullable=True, index=True)
    period_start = db.Column(db.Date, nullable=True)   # 결제 기간 시작일
    period_end = db.Column(db.Date, nullable=True)     # 결제 기간 종료일

    # 계산 기준
    weekly_fee = db.Column(db.Integer, nullable=True)  # 주당 수업료
    weeks_count = db.Column(db.Integer, nullable=True) # 적용 주차 수

    # 중간 합류 여부
    is_prorated = db.Column(db.Boolean, default=False) # True: 분기/월 중간 합류 결제

    # 조정 차감 내역
    carried_over = db.Column(db.Integer, default=0)   # 이월로 차감된 회차 수
    free_used = db.Column(db.Integer, default=0)      # 무료수업으로 차감된 회차 수

    # 관리자 임의 조정 메모
    manual_discount_note = db.Column(db.Text, nullable=True)

    # 문자 발송 이력
    sms_sent_at = db.Column(db.DateTime, nullable=True)

    # 결제 방법
    payment_method = db.Column(db.String(50), nullable=True)  # card, cash, transfer, etc

    # 결제 상태
    # pending: 청구 완료, 입금 대기
    # completed: 납부 완료
    # cancelled: 취소
    # refunded: 환불
    status = db.Column(db.String(20), default='pending', index=True)

    # 거래 정보
    transaction_id = db.Column(db.String(100), unique=True, nullable=True)  # 외부 결제 시스템 트랜잭션 ID
    receipt_url = db.Column(db.String(500), nullable=True)  # 영수증 URL

    # 결제 일시
    paid_at = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.Date, nullable=True)  # 납부 기한

    # 환불 정보
    refunded_at = db.Column(db.DateTime, nullable=True)
    refund_amount = db.Column(db.Integer, default=0)
    refund_reason = db.Column(db.Text, nullable=True)

    # 메모
    notes = db.Column(db.Text, nullable=True)

    # 처리자 정보
    processed_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'))

    # 메타 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    enrollment = db.relationship('CourseEnrollment', back_populates='payments')
    course = db.relationship('Course', backref='payments')
    student = db.relationship('Student', backref='payments')
    processor = db.relationship('User', foreign_keys=[processed_by])

    def __repr__(self):
        return f'<Payment {self.payment_id}: {self.amount}원>'

    def __init__(self, **kwargs):
        super(Payment, self).__init__(**kwargs)
        if not self.payment_id:
            self.payment_id = str(uuid.uuid4())

    @property
    def is_paid(self):
        """결제 완료 여부"""
        return self.status == 'completed'

    @property
    def is_overdue(self):
        """연체 여부"""
        if self.status == 'completed' or not self.due_date:
            return False
        return datetime.utcnow().date() > self.due_date

    @property
    def net_amount(self):
        """환불 후 순 금액"""
        return self.amount - self.refund_amount
