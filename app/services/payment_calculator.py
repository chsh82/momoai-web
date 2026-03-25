# -*- coding: utf-8 -*-
"""결제 계산 엔진 (PaymentCalculator)

사용 예:
    result = PaymentCalculator.calculate(enrollment, period)
    print(result.final_amount)
    print(result.to_dict())
"""
from datetime import timedelta
from app.models.session_adjustment import SessionAdjustment
from app.models.payment_period import HolidayWeek


# 할인 유형 한글 레이블
DISCOUNT_LABELS = {
    'sibling': '형제자매 할인',
    'acquaintance': '지인 할인',
    'employee': '직원 할인',
    'scholarship': '장학 할인',
}


class PaymentCalculationResult:
    """계산 결과 DTO"""

    def __init__(self):
        self.enrollment_id = None
        self.period_id = None

        # 수업료 기준
        self.weekly_fee = 0
        self.weeks_in_period = 0     # 해당 기간 전체 수업 주차 (휴무 제외)
        self.weeks_charged = 0       # 실제 청구 주차 (중간 합류 시 감소)
        self.is_prorated = False     # 중간 합류 여부

        # 기본 금액
        self.base_amount = 0         # weekly_fee × weeks_charged

        # 분기 결제 할인 (payment_cycle='quarterly' 시 주당 -5,000원)
        self.quarterly_discount = 0

        # 비율 할인 (형제자매/지인/직원/장학)
        self.discount_type = None
        self.discount_rate = 0.0
        self.percent_discount_amount = 0

        # 합산
        self.total_discount = 0      # quarterly_discount + percent_discount_amount
        self.subtotal = 0            # base_amount - total_discount

        # 이월/무료수업 차감
        self.rollover_sessions = 0
        self.free_sessions = 0
        self.adjustment_deduction = 0  # 차감 금액

        # 최종 금액
        self.final_amount = 0        # max(0, subtotal - adjustment_deduction)

        # 적용 대상 조정 목록 (Payment 저장 시 applied 처리에 사용)
        self.pending_adjustments = []

    @property
    def discount_label(self):
        return DISCOUNT_LABELS.get(self.discount_type, '할인 없음')

    def to_dict(self):
        return {
            'enrollment_id': self.enrollment_id,
            'period_id': self.period_id,
            'weekly_fee': self.weekly_fee,
            'weeks_in_period': self.weeks_in_period,
            'weeks_charged': self.weeks_charged,
            'is_prorated': self.is_prorated,
            'base_amount': self.base_amount,
            'quarterly_discount': self.quarterly_discount,
            'discount_type': self.discount_type,
            'discount_label': self.discount_label,
            'discount_rate': self.discount_rate,
            'percent_discount_amount': self.percent_discount_amount,
            'total_discount': self.total_discount,
            'subtotal': self.subtotal,
            'rollover_sessions': self.rollover_sessions,
            'free_sessions': self.free_sessions,
            'adjustment_deduction': self.adjustment_deduction,
            'final_amount': self.final_amount,
        }


class PaymentCalculator:
    """결제 계산 엔진

    계산 순서:
    1. 기간 내 수업 주차 수 계산 (휴무 주 제외, 중간 합류 고려)
    2. 기본 금액 = weekly_fee × weeks_charged
    3. 분기 할인 = 5,000원 × weeks_charged (payment_cycle='quarterly' 시)
    4. 비율 할인 = (base - quarterly_discount) × discount_rate
    5. subtotal = base - total_discount
    6. 조정 차감 = (이월 회차 + 무료수업 회차) × 회당 단가
    7. 최종 금액 = max(0, subtotal - 조정 차감)
    """

    # 비율 할인 설정
    DISCOUNT_RATES = {
        'sibling': 0.10,       # 형제자매 10%
        'acquaintance': 0.20,  # 지인 20%
        'employee': 0.50,      # 직원 50%
        'scholarship': 1.00,   # 장학 100%
    }

    # 분기 결제 주당 할인액
    QUARTERLY_DISCOUNT_PER_WEEK = 5000

    @classmethod
    def calculate(cls, enrollment, period):
        """선불 방식 수강료 계산.

        청구 기간(period)의 예정된 수업 주차 수를 기준으로 금액을 산출하고,
        period.start_date 이전에 발생한 pending 조정(이월/무료수업)을 차감한다.

        Args:
            enrollment: CourseEnrollment (payment_cycle, weekly_fee, discount_type, course 필요)
            period: PaymentPeriod (미래 또는 당월 기간)
        Returns:
            PaymentCalculationResult
        """
        result = PaymentCalculationResult()
        result.enrollment_id = enrollment.enrollment_id
        result.period_id = period.period_id

        # 1. 주당 수업료
        weekly_fee = enrollment.weekly_fee or 0
        result.weekly_fee = weekly_fee

        # 2. 기간 전체 수업 주차 수 (휴무 제외)
        weeks_in_period = cls._count_class_weeks(enrollment, period, period.start_date)
        result.weeks_in_period = weeks_in_period

        # 중간 합류 여부: 수강 시작일이 기간 시작일보다 늦으면 pro-rate
        enrolled_date = enrollment.enrolled_at.date() if enrollment.enrolled_at else None
        if enrolled_date and enrolled_date > period.start_date:
            weeks_charged = cls._count_class_weeks(enrollment, period, enrolled_date)
            result.is_prorated = True
        else:
            weeks_charged = weeks_in_period
        result.weeks_charged = weeks_charged

        # 3. 기본 금액
        base_amount = weekly_fee * weeks_charged
        result.base_amount = base_amount

        # 4. 분기 결제 할인 (quarterly_no_discount는 할인 미적용)
        quarterly_discount = 0
        if enrollment.payment_cycle == 'quarterly':
            quarterly_discount = cls.QUARTERLY_DISCOUNT_PER_WEEK * weeks_charged
        result.quarterly_discount = quarterly_discount

        # 5. 비율 할인 (기본금액 - 분기할인 기준으로 계산)
        after_quarterly = base_amount - quarterly_discount
        discount_type = getattr(enrollment, 'discount_type', None)
        discount_rate = cls.DISCOUNT_RATES.get(discount_type, 0.0)
        percent_discount_amount = round(after_quarterly * discount_rate)

        result.discount_type = discount_type
        result.discount_rate = discount_rate
        result.percent_discount_amount = percent_discount_amount
        result.total_discount = quarterly_discount + percent_discount_amount
        result.subtotal = max(0, base_amount - result.total_discount)

        # 6. 이월/무료수업 차감
        # 선불 방식: 청구 기간 시작일 이전에 발생한 pending 조정만 반영
        # (당월 기간 중 발생하는 미래 조정은 다음 기간 청구서에서 처리)
        adjustments = SessionAdjustment.get_pending_before(
            enrollment.enrollment_id, period.start_date
        )
        rollover_sessions = sum(a.sessions_count for a in adjustments
                                if a.adjustment_type == 'rollover')
        free_sessions = sum(a.sessions_count for a in adjustments
                            if a.adjustment_type == 'free_session')
        total_adjust_sessions = rollover_sessions + free_sessions

        # 회당 단가 = subtotal ÷ weeks_charged (할인 적용된 단가)
        per_session_rate = (result.subtotal / weeks_charged) if weeks_charged > 0 else 0
        adjustment_deduction = round(per_session_rate * total_adjust_sessions)

        result.rollover_sessions = rollover_sessions
        result.free_sessions = free_sessions
        result.adjustment_deduction = adjustment_deduction
        result.pending_adjustments = adjustments

        # 7. 최종 금액
        result.final_amount = max(0, result.subtotal - adjustment_deduction)

        return result

    @classmethod
    def calculate_batch(cls, enrollments, period):
        """여러 enrollment를 한 번에 계산

        Returns:
            list of (enrollment, PaymentCalculationResult)
        """
        return [(e, cls.calculate(e, period)) for e in enrollments]

    @classmethod
    def _get_holiday_mondays(cls, period):
        """기간 내 휴무 주 월요일 집합"""
        holiday_weeks = HolidayWeek.query.filter(
            HolidayWeek.week_start >= period.start_date,
            HolidayWeek.week_start <= period.end_date
        ).all()
        return {hw.week_start for hw in holiday_weeks}

    @classmethod
    def _count_class_weeks(cls, enrollment, period, from_date):
        """from_date ~ period.end_date 사이 수업 요일 등장 횟수 (휴무 주 제외)

        Args:
            enrollment: CourseEnrollment
            period: PaymentPeriod
            from_date: 계산 시작일 (중간 합류 시 수강 시작일)
        Returns:
            int: 수업 주차 수
        """
        course = enrollment.course
        if not course or course.weekday is None:
            # 수업 요일 미지정 시 기간의 effective_weeks 사용
            if from_date <= period.start_date:
                return period.effective_weeks
            # pro-rate: 남은 기간 비율 계산
            total_days = (period.end_date - period.start_date).days + 1
            remain_days = (period.end_date - from_date).days + 1
            return round(period.effective_weeks * remain_days / total_days)

        weekday = course.weekday  # 0=월 ~ 6=일
        holiday_mondays = cls._get_holiday_mondays(period)

        # from_date 이후 첫 번째 수업 요일 찾기
        effective_start = max(from_date, period.start_date)
        days_ahead = (weekday - effective_start.weekday()) % 7
        first_class = effective_start + timedelta(days=days_ahead)

        if first_class > period.end_date:
            return 0

        count = 0
        current = first_class
        while current <= period.end_date:
            # 이 날이 속한 주의 월요일
            monday = current - timedelta(days=current.weekday())
            if monday not in holiday_mondays:
                count += 1
            current += timedelta(weeks=1)

        return count

    @classmethod
    def get_discount_options(cls):
        """할인 유형 선택지 (템플릿용)"""
        return [
            ('', '할인 없음'),
            ('sibling', '형제자매 할인 (10%)'),
            ('acquaintance', '지인 할인 (20%)'),
            ('employee', '직원 할인 (50%)'),
            ('scholarship', '장학 할인 (100%)'),
        ]

    @classmethod
    def get_payment_cycle_options(cls):
        """결제 주기 선택지 (템플릿용)"""
        return [
            ('monthly', '월별'),
            ('quarterly', '분기별 (-5,000원/주)'),
            ('quarterly_no_discount', '분기별 (할인없음)'),
        ]
