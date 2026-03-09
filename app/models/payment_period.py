# -*- coding: utf-8 -*-
"""PaymentPeriod, HolidayWeek 모델"""
from datetime import datetime, date, timedelta
import uuid
from app.models import db


class PaymentPeriod(db.Model):
    """결제 기간 캘린더 모델 (월별/분기별)"""
    __tablename__ = 'payment_periods'

    period_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 기간 유형
    period_type = db.Column(db.String(20), nullable=False, index=True)  # 'monthly', 'quarterly'

    # 연도 및 기간 번호
    year = db.Column(db.Integer, nullable=False, index=True)
    period_number = db.Column(db.Integer, nullable=False)
    # monthly: 1~12 (월), quarterly: 1~4 (분기)

    # 표시 레이블
    label = db.Column(db.String(50), nullable=False)
    # 예: "2026년 3월", "2026년 2분기 (4~6월)"

    # 기간 날짜
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    # 주차 수
    weeks_count = db.Column(db.Integer, nullable=False, default=12)
    # monthly: 해당 월 주차 수, quarterly: 12 or 13

    # 수동 수정 여부
    is_adjusted = db.Column(db.Boolean, default=False)
    adjusted_note = db.Column(db.String(200), nullable=True)  # 수정 사유

    # 메타
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    payments = db.relationship('Payment', backref='period', lazy='dynamic')

    def __repr__(self):
        return f'<PaymentPeriod {self.label}>'

    def __init__(self, **kwargs):
        super(PaymentPeriod, self).__init__(**kwargs)
        if not self.period_id:
            self.period_id = str(uuid.uuid4())

    @property
    def holiday_weeks(self):
        """기간 내 휴무 주 목록"""
        return HolidayWeek.query.filter(
            HolidayWeek.week_start >= self.start_date,
            HolidayWeek.week_start <= self.end_date
        ).all()

    @property
    def effective_weeks(self):
        """휴무 주 제외 실제 수업 주차 수"""
        return self.weeks_count - len(self.holiday_weeks)

    @classmethod
    def generate_monthly(cls, year):
        """해당 연도 월별 기간 12개 자동 생성"""
        import calendar
        periods = []
        for month in range(1, 13):
            first_day = date(year, month, 1)
            last_day = date(year, month, calendar.monthrange(year, month)[1])

            # 주차 수 계산: 월요일 기준 몇 주가 걸치는지
            weeks = cls._count_weeks_in_range(first_day, last_day)

            label = f'{year}년 {month}월'
            period = cls(
                period_type='monthly',
                year=year,
                period_number=month,
                label=label,
                start_date=first_day,
                end_date=last_day,
                weeks_count=weeks
            )
            periods.append(period)
        return periods

    @classmethod
    def generate_quarterly(cls, year):
        """해당 연도 분기별 기간 4개 자동 생성 (기본 12주)
        1분기: 12월(전년)~2월, 2분기: 3~5월, 3분기: 6~8월, 4분기: 9~11월
        """
        quarter_starts = [
            (1, date(year - 1, 12, 1), '(12~2월)'),  # 1분기: 전년 12월 시작
            (2, date(year, 3, 1),      '(3~5월)'),   # 2분기: 3월
            (3, date(year, 6, 1),      '(6~8월)'),   # 3분기: 6월
            (4, date(year, 9, 1),      '(9~11월)'),  # 4분기: 9월
        ]

        periods = []
        for q_num, start_date, label_suffix in quarter_starts:
            start = cls._get_monday(start_date)
            end = start + timedelta(weeks=12) - timedelta(days=1)

            label = f'{year}년 {q_num}분기 {label_suffix}'
            period = cls(
                period_type='quarterly',
                year=year,
                period_number=q_num,
                label=label,
                start_date=start,
                end_date=end,
                weeks_count=12
            )
            periods.append(period)
        return periods

    @staticmethod
    def _get_monday(d):
        """해당 날짜가 속한 주의 월요일 반환"""
        return d - timedelta(days=d.weekday())

    @staticmethod
    def _count_weeks_in_range(start, end):
        """날짜 범위 내 월요일 수 (주차 수) 계산"""
        count = 0
        current = start
        while current <= end:
            if current.weekday() == 0:  # 월요일
                count += 1
            current += timedelta(days=1)
        return count


class HolidayWeek(db.Model):
    """휴무 주 모델"""
    __tablename__ = 'holiday_weeks'

    holiday_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 해당 주 날짜 (월요일 ~ 일요일)
    week_start = db.Column(db.Date, nullable=False, index=True)  # 월요일
    week_end = db.Column(db.Date, nullable=False)                 # 일요일

    # 사유
    reason = db.Column(db.String(200), nullable=False)  # "추석 연휴", "설 연휴" 등

    # 등록자
    created_by = db.Column(db.String(36), db.ForeignKey('users.user_id', ondelete='SET NULL'),
                           nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<HolidayWeek {self.week_start} ~ {self.week_end}: {self.reason}>'

    def __init__(self, **kwargs):
        super(HolidayWeek, self).__init__(**kwargs)
        if not self.holiday_id:
            self.holiday_id = str(uuid.uuid4())
        # week_start로 week_end 자동 계산
        if self.week_start and not self.week_end:
            self.week_end = self.week_start + timedelta(days=6)
