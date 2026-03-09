#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""결제 시스템 테스트용 데이터 생성 + 청구서 생성 end-to-end 테스트"""
import sys
import uuid
from datetime import date, datetime, timedelta

PASS = '✅'
FAIL = '❌'
INFO = '  '

def ok(msg): print(f'  {PASS} {msg}')
def err(msg, e=''): print(f'  {FAIL} {msg}'); print(f'     → {e}') if e else None
def info(msg): print(f'  ℹ  {msg}')
def section(t): print(f'\n{"─"*55}\n  {t}\n{"─"*55}')


# ── Flask 앱 초기화 ──
section('0. Flask 앱 초기화')
try:
    from app import create_app
    app = create_app()
    app.app_context().push()
    ok('Flask 앱 생성')
except Exception as e:
    err('Flask 앱 생성 실패', str(e)); sys.exit(1)

from app.models import db, Student, Course, CourseEnrollment, Payment
from app.models.payment_period import PaymentPeriod, HolidayWeek
from app.models.session_adjustment import SessionAdjustment
from app.models.user import User


# ── 기존 테스트 데이터 정리 ──
section('1. 기존 테스트 데이터 정리')
old_students = Student.query.filter(Student.name.like('[테스트]%')).all()
if old_students:
    sids = [s.student_id for s in old_students]
    SessionAdjustment.query.filter(SessionAdjustment.student_id.in_(sids)).delete(synchronize_session=False)
    Payment.query.filter(Payment.student_id.in_(sids)).delete(synchronize_session=False)
    CourseEnrollment.query.filter(CourseEnrollment.student_id.in_(sids)).delete(synchronize_session=False)
    for s in old_students:
        db.session.delete(s)
    # 테스트 수업 정리
    for c in Course.query.filter(Course.course_code.like('TEST-%')).all():
        db.session.delete(c)
    db.session.commit()
    info(f'기존 테스트 데이터 {len(old_students)}건 삭제')
else:
    info('기존 테스트 데이터 없음')

# 테스트 기간 정리
PaymentPeriod.query.filter(PaymentPeriod.label.like('%테스트%')).delete(synchronize_session=False)
db.session.commit()


# ── 관리자/강사 확인 ──
admin = User.query.filter(User.role.in_(['admin', 'manager'])).first()
teacher = User.query.filter_by(role='teacher').first() or admin

if not admin:
    err('관리자 계정 없음 — DB에 users가 비어 있음'); sys.exit(1)

ok(f'관리자: {admin.username}')
ok(f'강사: {teacher.username if teacher else "없음(admin 사용)"}')
teacher_id = (teacher or admin).user_id


# ── 학생 5명 생성 ──
section('2. 테스트 학생 생성')
now = datetime.utcnow()
STUDENTS = [
    {'name': '[테스트]김모모', 'grade': '중2', 'phone': '01011110001'},
    {'name': '[테스트]이하나', 'grade': '고1', 'phone': '01011110002'},
    {'name': '[테스트]박준서', 'grade': '초5', 'phone': '01011110003'},
    {'name': '[테스트]최서연', 'grade': '중3', 'phone': '01011110004'},
    {'name': '[테스트]정우진', 'grade': '고2', 'phone': '01011110005'},
]
students = []
for sd in STUDENTS:
    s = Student(
        student_id=str(uuid.uuid4()),
        teacher_id=teacher_id,
        name=sd['name'], grade=sd['grade'], phone=sd['phone']
    )
    db.session.add(s)
    students.append(s)
db.session.commit()
ok(f'학생 {len(students)}명 생성: {", ".join(s.name for s in students)}')


# ── 수업 3개 생성 ──
section('3. 테스트 수업 생성')
COURSES = [
    {'name': '[테스트]정규반 화요일반', 'code': 'TEST-TUE-001', 'grade': '중등', 'type': '정규반', 'weekday': 1},
    {'name': '[테스트]프리미엄 목요일반', 'code': 'TEST-THU-001', 'grade': '고등', 'type': '프리미엄', 'weekday': 3},
    {'name': '[테스트]베이직 수요일반', 'code': 'TEST-WED-001', 'grade': '초등', 'type': '베이직', 'weekday': 2},
]
courses = []
for cd in COURSES:
    c = Course(
        course_id=str(uuid.uuid4()),
        course_name=cd['name'], course_code=cd['code'],
        grade=cd['grade'], course_type=cd['type'],
        weekday=cd['weekday'],
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        status='active', teacher_id=teacher_id,
        created_by=admin.user_id
    )
    db.session.add(c)
    courses.append(c)
db.session.commit()
ok(f'수업 {len(courses)}개 생성')
DAYS = ['월','화','수','목','금','토','일']
for c in courses:
    ok(f'  {c.course_name} ({DAYS[c.weekday]}요일)')


# ── 수강 등록 6건 (다양한 설정) ──
section('4. 수강 등록 + 결제 설정')
#  (course_idx, student_idx, payment_cycle, weekly_fee, discount_type, label)
ENROLLMENTS = [
    (0, 0, 'monthly',    80000, None,           '김모모 / 정규반 / 월별 / 할인없음'),
    (0, 1, 'quarterly',  80000, 'sibling',      '이하나 / 정규반 / 분기별 / 형제자매10%'),
    (1, 2, 'monthly',    50000, None,           '박준서 / 프리미엄 / 월별 / 할인없음'),
    (1, 3, 'monthly',    50000, 'acquaintance', '최서연 / 프리미엄 / 월별 / 지인20%'),
    (2, 4, 'quarterly',  35000, None,           '정우진 / 베이직 / 분기별 / 할인없음'),
    (0, 4, 'monthly',    80000, 'scholarship',  '정우진 / 정규반 / 월별 / 장학100%'),
]
enrollments = []
for cidx, sidx, cycle, fee, disc, label in ENROLLMENTS:
    e = CourseEnrollment(
        enrollment_id=str(uuid.uuid4()),
        course_id=courses[cidx].course_id,
        student_id=students[sidx].student_id,
        status='active',
        payment_cycle=cycle,
        weekly_fee=fee,
        discount_type=disc,
        enrolled_at=datetime(2026, 3, 1)
    )
    db.session.add(e)
    enrollments.append((e, label))
db.session.commit()
for e, label in enrollments:
    ok(f'{label}')


# ── 결제 기간 생성 (2026년 3월 월별) ──
section('5. 결제 기간 생성')
import calendar
y, m = 2026, 3
first_day = date(y, m, 1)
last_day = date(y, m, calendar.monthrange(y, m)[1])

# 주차 수 계산 (월요일 기준)
weeks = sum(1 for d in (first_day + timedelta(n) for n in range((last_day - first_day).days + 1))
            if d.weekday() == 0)

period_monthly = PaymentPeriod(
    period_id=str(uuid.uuid4()),
    period_type='monthly',
    year=y, period_number=m,
    label=f'{y}년 {m}월 [테스트]',
    start_date=first_day, end_date=last_day,
    weeks_count=weeks
)
db.session.add(period_monthly)

# 분기별 기간도 생성 (1분기 3~5월, 2026-03-02 월요일 기준)
q_start = date(2026, 3, 2)  # 2026년 3월 첫 번째 월요일
q_end = q_start + timedelta(weeks=12) - timedelta(days=1)
period_quarterly = PaymentPeriod(
    period_id=str(uuid.uuid4()),
    period_type='quarterly',
    year=2026, period_number=1,
    label='2026년 1분기 (3~5월) [테스트]',
    start_date=q_start, end_date=q_end,
    weeks_count=12
)
db.session.add(period_quarterly)
db.session.commit()

ok(f'월별 기간: {period_monthly.label} ({first_day}~{last_day}, {weeks}주, 유효 {period_monthly.effective_weeks}주)')
ok(f'분기별 기간: {period_quarterly.label} ({q_start}~{q_end}, 12주, 유효 {period_quarterly.effective_weeks}주)')


# ── 계산 엔진으로 미리보기 ──
section('6. PaymentCalculator 계산 미리보기')
from app.services.payment_calculator import PaymentCalculator

print(f'\n  {'─'*50}')
print(f'  {"수강생 / 수업":<22} {"기간":<8} {"기본금":>8} {"할인":>8} {"최종금":>9}')
print(f'  {"─"*50}')

calc_results = []
for e, label in enrollments:
    period = period_quarterly if e.payment_cycle == 'quarterly' else period_monthly
    result = PaymentCalculator.calculate(e, period)
    calc_results.append((e, label, result, period))

    disc_str = f'-{result.total_discount:,}' if result.total_discount else '-'
    period_label = '분기' if period.period_type == 'quarterly' else '월별'
    print(f'  {label[:22]:<22} {period_label:<8} {result.base_amount:>8,} {disc_str:>8} {result.final_amount:>9,}원')

print(f'  {"─"*50}')
total = sum(r.final_amount for _, _, r, _ in calc_results)
print(f'  {"합계":>40} {total:>9,}원')


# ── 청구서 생성 (Payment 레코드) ──
section('7. 청구서 생성')
created = []
for e, label, result, period in calc_results:
    payment = Payment(
        payment_id=str(uuid.uuid4()),
        enrollment_id=e.enrollment_id,
        course_id=e.course_id,
        student_id=e.student_id,
        amount=result.final_amount,
        original_amount=result.base_amount,
        discount_type=result.discount_type,
        discount_rate=result.discount_rate,
        discount_amount=result.total_discount,
        payment_type='tuition',
        payment_period=e.payment_cycle,
        period_id=period.period_id,
        period_start=period.start_date,
        period_end=period.end_date,
        weekly_fee=result.weekly_fee,
        weeks_count=result.weeks_charged,
        is_prorated=result.is_prorated,
        carried_over=result.rollover_sessions,
        free_used=result.free_sessions,
        status='pending',
        processed_by=admin.user_id,
    )
    db.session.add(payment)
    created.append((label, payment))

db.session.commit()
ok(f'청구서 {len(created)}건 생성 완료')
for label, p in created:
    ok(f'  {label} → {p.amount:,}원 ({p.status})')


# ── SMS 미리보기 ──
section('8. SMS 문자 내용 미리보기')
from app.admin.routes import _build_sms_message

for label, p in created[:3]:  # 처음 3건만
    msg = _build_sms_message(p)
    print(f'\n  [{label}]')
    for line in msg.splitlines():
        print(f'  │ {line}')
    print(f'  └ 총 {len(msg)}자 ({("LMS" if len(msg) > 90 else "SMS")})')


# ── 최종 검증 ──
section('9. 최종 검증')
pay_count = Payment.query.filter_by(payment_type='tuition', status='pending').count()
ok(f'DB 저장 확인: pending 청구서 {pay_count}건')

total_pending = sum(p.amount for _, p in created)
ok(f'총 청구 금액: {total_pending:,}원')

# 수강생별 확인
for e, label, result, period in calc_results:
    p_in_db = Payment.query.filter_by(enrollment_id=e.enrollment_id, period_id=period.period_id).first()
    if p_in_db:
        ok(f'  {label[:28]} → DB 저장됨 (payment_id: {p_in_db.payment_id[:8]}...)')
    else:
        err(f'  {label} → DB에서 찾을 수 없음')

print(f'\n{"═"*55}')
print('  테스트 완료! 관리자 페이지에서 확인하세요:')
print('  → /admin/billing?period_id=' + period_monthly.period_id)
print(f'{"═"*55}\n')
