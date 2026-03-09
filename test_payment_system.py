#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""결제 시스템 전체 테스트 스크립트"""
import sys
import traceback
from datetime import date, datetime, timedelta

PASS = '✅'
FAIL = '❌'
WARN = '⚠️ '

results = []

def ok(section, msg):
    results.append((PASS, section, msg))
    print(f'  {PASS} {msg}')

def fail(section, msg, detail=''):
    results.append((FAIL, section, msg))
    print(f'  {FAIL} {msg}')
    if detail:
        print(f'     → {detail}')

def warn(section, msg):
    results.append((WARN, section, msg))
    print(f'  {WARN} {msg}')

def section(title):
    print(f'\n{"─"*55}')
    print(f'  {title}')
    print(f'{"─"*55}')


# ════════════════════════════════════════════════════════
# 0. Flask 앱 초기화
# ════════════════════════════════════════════════════════
section('0. Flask 앱 초기화')
try:
    from app import create_app
    app = create_app()
    ctx = app.app_context()
    ctx.push()
    ok('init', 'Flask 앱 생성 성공')
except Exception as e:
    print(f'  {FAIL} Flask 앱 생성 실패: {e}')
    sys.exit(1)


# ════════════════════════════════════════════════════════
# 1. DB 스키마 검증
# ════════════════════════════════════════════════════════
section('1. DB 스키마 검증')
import sqlite3
from flask import current_app

db_path = current_app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
if not db_path:
    db_path = 'momoai.db'

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    required_tables = [
        'payment_periods', 'holiday_weeks', 'session_adjustments',
        'payments', 'course_enrollments', 'attendance'
    ]
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {r[0] for r in cur.fetchall()}

    for tbl in required_tables:
        if tbl in existing:
            ok('schema', f'테이블 존재: {tbl}')
        else:
            fail('schema', f'테이블 없음: {tbl}')

    # 컬럼 확인
    col_checks = [
        ('course_enrollments', 'payment_cycle'),
        ('course_enrollments', 'weekly_fee'),
        ('course_enrollments', 'discount_type'),
        ('payments', 'period_id'),
        ('payments', 'period_start'),
        ('payments', 'period_end'),
        ('payments', 'weekly_fee'),
        ('payments', 'weeks_count'),
        ('payments', 'is_prorated'),
        ('payments', 'carried_over'),
        ('payments', 'free_used'),
        ('payments', 'sms_sent_at'),
        ('attendance', 'adjustment_created'),
    ]
    for tbl, col in col_checks:
        cur.execute(f'PRAGMA table_info({tbl})')
        cols = {r[1] for r in cur.fetchall()}
        if col in cols:
            ok('schema', f'컬럼 존재: {tbl}.{col}')
        else:
            fail('schema', f'컬럼 없음: {tbl}.{col}')

    conn.close()
except Exception as e:
    fail('schema', f'DB 스키마 확인 실패: {e}')


# ════════════════════════════════════════════════════════
# 2. 모델 임포트 및 쿼리
# ════════════════════════════════════════════════════════
section('2. 모델 임포트 및 기본 쿼리')
try:
    from app.models.payment_period import PaymentPeriod, HolidayWeek
    ok('model', 'PaymentPeriod, HolidayWeek 임포트 성공')
except Exception as e:
    fail('model', f'PaymentPeriod 임포트 실패: {e}')

try:
    from app.models.session_adjustment import SessionAdjustment
    ok('model', 'SessionAdjustment 임포트 성공')
except Exception as e:
    fail('model', f'SessionAdjustment 임포트 실패: {e}')

try:
    from app.models import Payment, CourseEnrollment
    ok('model', 'Payment, CourseEnrollment 임포트 성공')
except Exception as e:
    fail('model', f'Payment 임포트 실패: {e}')

try:
    cnt_periods = PaymentPeriod.query.count()
    cnt_holiday = HolidayWeek.query.count()
    cnt_adj = SessionAdjustment.query.count()
    cnt_pay = Payment.query.count()
    ok('query', f'PaymentPeriod: {cnt_periods}건')
    ok('query', f'HolidayWeek: {cnt_holiday}건')
    ok('query', f'SessionAdjustment: {cnt_adj}건')
    ok('query', f'Payment (tuition): {Payment.query.filter_by(payment_type="tuition").count()}건')
except Exception as e:
    fail('query', f'기본 쿼리 실패: {e}', traceback.format_exc().splitlines()[-1])


# ════════════════════════════════════════════════════════
# 3. PaymentPeriod 자동 생성 로직
# ════════════════════════════════════════════════════════
section('3. PaymentPeriod 자동 생성 로직')
try:
    monthly = PaymentPeriod.generate_monthly(2026)
    assert len(monthly) == 12, f'월별 12개여야 함, 실제: {len(monthly)}'
    ok('period', f'월별 자동 생성: {len(monthly)}개')

    for p in monthly:
        assert p.start_date.month == p.period_number, f'{p.label} start_date 불일치'
        assert p.weeks_count >= 4, f'{p.label} weeks_count 이상: {p.weeks_count}'
    ok('period', f'월별 날짜/주차 검증 통과 (1~12월)')

    quarterly = PaymentPeriod.generate_quarterly(2026)
    assert len(quarterly) == 4, f'분기 4개여야 함, 실제: {len(quarterly)}'
    ok('period', f'분기별 자동 생성: {len(quarterly)}개')

    for p in quarterly:
        assert p.weeks_count == 12, f'{p.label} weeks_count가 12여야 함: {p.weeks_count}'
        assert p.start_date.weekday() == 0, f'{p.label} 시작일이 월요일이어야 함: {p.start_date}'
    ok('period', '분기별 12주·월요일 시작 검증 통과')

except AssertionError as e:
    fail('period', f'자동 생성 검증 실패: {e}')
except Exception as e:
    fail('period', f'자동 생성 오류: {e}', traceback.format_exc().splitlines()[-1])


# ════════════════════════════════════════════════════════
# 4. PaymentCalculator 계산 엔진
# ════════════════════════════════════════════════════════
section('4. PaymentCalculator 계산 엔진')
try:
    from app.services.payment_calculator import PaymentCalculator, PaymentCalculationResult
    ok('calc', 'PaymentCalculator 임포트 성공')
except Exception as e:
    fail('calc', f'PaymentCalculator 임포트 실패: {e}')
    PaymentCalculator = None

if PaymentCalculator:
    # Mock 오브젝트로 단위 테스트
    class MockCourse:
        weekday = 1  # 화요일

    class MockEnrollment:
        enrollment_id = 'test-enroll-001'
        course = MockCourse()
        payment_cycle = 'monthly'
        weekly_fee = 100000
        discount_type = None
        enrolled_at = datetime(2026, 3, 1)

    class MockPeriod:
        period_id = 'test-period-001'
        period_type = 'monthly'
        start_date = date(2026, 3, 1)
        end_date = date(2026, 3, 31)
        weeks_count = 4
        effective_weeks = 4

    try:
        enroll = MockEnrollment()
        period = MockPeriod()

        # HolidayWeek mock 패치 (DB 쿼리 없이)
        original_holiday = PaymentCalculator._get_holiday_mondays
        PaymentCalculator._get_holiday_mondays = classmethod(lambda cls, p: set())

        result = PaymentCalculator.calculate(enroll, period)

        assert isinstance(result, PaymentCalculationResult), '반환 타입 오류'
        assert result.weekly_fee == 100000, f'weekly_fee 오류: {result.weekly_fee}'
        assert result.weeks_charged >= 1, f'weeks_charged 오류: {result.weeks_charged}'
        assert result.quarterly_discount == 0, f'월별인데 quarterly_discount != 0: {result.quarterly_discount}'
        assert result.percent_discount_amount == 0, f'할인없는데 discount > 0: {result.percent_discount_amount}'
        assert result.final_amount == result.base_amount, f'조정없는데 final != base'
        ok('calc', f'기본 계산 통과: 화요일 {result.weeks_charged}주 × 100,000원 = {result.final_amount:,}원')

        # 분기 할인 테스트
        enroll.payment_cycle = 'quarterly'
        result2 = PaymentCalculator.calculate(enroll, period)
        expected_qdisc = 5000 * result2.weeks_charged
        assert result2.quarterly_discount == expected_qdisc, \
            f'분기할인 오류: {result2.quarterly_discount} != {expected_qdisc}'
        ok('calc', f'분기 할인 통과: -{result2.quarterly_discount:,}원 ({result2.weeks_charged}주 × 5,000원)')

        # 비율 할인 테스트
        enroll.payment_cycle = 'monthly'
        enroll.discount_type = 'sibling'
        result3 = PaymentCalculator.calculate(enroll, period)
        expected_pct = round(result3.base_amount * 0.10)
        assert result3.percent_discount_amount == expected_pct, \
            f'형제자매 할인 오류: {result3.percent_discount_amount} != {expected_pct}'
        ok('calc', f'형제자매 10% 할인 통과: -{result3.percent_discount_amount:,}원')

        enroll.discount_type = 'scholarship'
        result4 = PaymentCalculator.calculate(enroll, period)
        assert result4.final_amount == 0, f'장학 100% 할인 후 최종금액이 0이어야 함: {result4.final_amount}'
        ok('calc', '장학 100% 할인 통과: 최종 금액 0원')

        # to_dict() 검증
        d = result.to_dict()
        required_keys = ['enrollment_id', 'period_id', 'weekly_fee', 'weeks_charged',
                         'base_amount', 'total_discount', 'final_amount']
        missing = [k for k in required_keys if k not in d]
        if missing:
            fail('calc', f'to_dict() 누락 키: {missing}')
        else:
            ok('calc', 'to_dict() 필수 키 검증 통과')

        # mock 복원
        PaymentCalculator._get_holiday_mondays = original_holiday

    except AssertionError as e:
        fail('calc', f'계산 검증 실패: {e}')
    except Exception as e:
        fail('calc', f'계산 오류: {e}', traceback.format_exc().splitlines()[-1])


# ════════════════════════════════════════════════════════
# 5. SessionAdjustment 상태 흐름
# ════════════════════════════════════════════════════════
section('5. SessionAdjustment 상태 및 메서드')
try:
    # 레이블 검증
    s = SessionAdjustment()
    s.adjustment_type = 'rollover'
    s.status = 'pending_review'
    s.source = 'teacher_excused'
    s.sessions_count = 2

    assert s.type_label == '이월', f'type_label 오류: {s.type_label}'
    assert s.status_label == '분류 대기', f'status_label 오류: {s.status_label}'
    assert s.source_label == '강사 인정결석', f'source_label 오류: {s.source_label}'
    ok('adj', 'type_label / status_label / source_label 검증 통과')

    s.adjustment_type = 'free_session'
    s.status = 'applied'
    s.source = 'admin_manual'
    assert s.type_label == '무료수업', f'type_label 오류: {s.type_label}'
    assert s.status_label == '적용 완료', f'status_label 오류: {s.status_label}'
    assert s.source_label == '관리자 입력', f'source_label 오류: {s.source_label}'
    ok('adj', 'free_session / applied / admin_manual 레이블 검증 통과')

    cnt_review = SessionAdjustment.get_pending_review_count()
    ok('adj', f'get_pending_review_count() 실행 성공: {cnt_review}건')

except AssertionError as e:
    fail('adj', f'SessionAdjustment 검증 실패: {e}')
except Exception as e:
    fail('adj', f'SessionAdjustment 오류: {e}', traceback.format_exc().splitlines()[-1])


# ════════════════════════════════════════════════════════
# 6. SMS 헬퍼 함수
# ════════════════════════════════════════════════════════
section('6. SMS 헬퍼 함수')
try:
    from app.admin.routes import _build_sms_message, _get_sms_recipient

    class MockStudent:
        name = '테스트학생'
        phone = '01099998888'
        student_id = 'mock-student-id'

    class MockCourseForSms:
        course_name = '정규반 화요일'

    class MockPayment:
        student = MockStudent()
        course = MockCourseForSms()
        student_id = 'mock-student-id'
        amount = 120000
        original_amount = 130000
        discount_type = 'sibling'
        discount_amount = 10000
        discount_rate = 0.1
        carried_over = 1
        free_used = 0
        weekly_fee = 30000
        period_start = date(2026, 3, 1)
        period_end = date(2026, 3, 31)
        sms_sent_at = None

    msg = _build_sms_message(MockPayment())
    assert '[momoAI 수강료 안내]' in msg, 'SMS 헤더 없음'
    assert '테스트학생' in msg, '학생명 없음'
    assert '120,000원' in msg, '금액 없음'
    assert '정규반 화요일' in msg, '수업명 없음'
    ok('sms', f'_build_sms_message() 생성 성공 ({len(msg)}자)')
    ok('sms', f'  내용 미리보기:\n{chr(10).join("    " + l for l in msg.splitlines())}')

    # 90자 SMS vs LMS 분기
    assert len(msg) > 0, 'SMS 내용 비어 있음'
    msg_type = 'LMS' if len(msg) > 90 else 'SMS'
    ok('sms', f'메시지 유형: {msg_type} ({len(msg)}자)')

except Exception as e:
    fail('sms', f'SMS 헬퍼 오류: {e}', traceback.format_exc().splitlines()[-1])


# ════════════════════════════════════════════════════════
# 7. 라우트 등록 확인
# ════════════════════════════════════════════════════════
section('7. 라우트 등록 확인')
try:
    url_map = {rule.endpoint: rule.rule for rule in app.url_map.iter_rules()}

    required_routes = [
        ('admin.billing', '/admin/billing'),
        ('admin.create_invoices', '/admin/billing/create-invoices'),
        ('admin.payment_sms_preview', '/admin/api/payment/<payment_id>/sms-preview'),
        ('admin.send_payment_sms', '/admin/billing/send-sms'),
        ('admin.send_payment_sms_batch', '/admin/billing/send-sms-batch'),
        ('admin.payment_periods', '/admin/payment-periods'),
        ('admin.session_adjustments', '/admin/session-adjustments'),
        ('admin.calculate_enrollment_payment', '/admin/api/enrollment/<enrollment_id>/calculate'),
        ('admin.update_enrollment_payment_info', '/admin/api/enrollment/<enrollment_id>/update-payment-info'),
        ('parent.child_payments', '/parent/children/<student_id>/payments'),
        ('parent.all_payments', '/parent/payments'),
        ('student.my_payments', '/student/payments'),
    ]

    for endpoint, expected_path in required_routes:
        if endpoint in url_map:
            ok('route', f'{endpoint}')
        else:
            fail('route', f'라우트 미등록: {endpoint}')

except Exception as e:
    fail('route', f'라우트 확인 실패: {e}')


# ════════════════════════════════════════════════════════
# 8. 템플릿 파일 존재 확인
# ════════════════════════════════════════════════════════
section('8. 템플릿 파일 존재 확인')
import os

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
required_templates = [
    'admin/billing.html',
    'admin/payment_periods.html',
    'admin/session_adjustments.html',
    'parent/child_payments.html',
    'parent/all_payments.html',
    'student/my_payments.html',
]
for tpl in required_templates:
    path = os.path.join(template_dir, tpl)
    if os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        ok('template', f'{tpl} ({size_kb}KB)')
    else:
        fail('template', f'템플릿 없음: {tpl}')


# ════════════════════════════════════════════════════════
# 9. 실제 DB 데이터로 결합 테스트
# ════════════════════════════════════════════════════════
section('9. 실제 DB 데이터 결합 테스트')
try:
    from app.models import CourseEnrollment

    # payment_cycle + weekly_fee 설정된 enrollment 확인
    configured = CourseEnrollment.query.filter(
        CourseEnrollment.payment_cycle.isnot(None),
        CourseEnrollment.weekly_fee.isnot(None)
    ).all()

    if configured:
        ok('live', f'결제 설정 완료 enrollment: {len(configured)}건')

        # 기간이 있으면 실제 계산 실행
        period = PaymentPeriod.query.order_by(PaymentPeriod.start_date.desc()).first()
        if period:
            ok('live', f'최신 결제 기간: {period.label} (유효 {period.effective_weeks}주)')
            enroll = configured[0]
            try:
                result = PaymentCalculator.calculate(enroll, period)
                ok('live', f'실제 계산 성공: {enroll.student.name if enroll.student else "?"} → {result.final_amount:,}원')
                ok('live', f'  주당 {result.weekly_fee:,}원 × {result.weeks_charged}주'
                           f' - 할인 {result.total_discount:,}원 - 조정 {result.adjustment_deduction:,}원')
            except Exception as e:
                fail('live', f'실제 계산 실패: {e}', traceback.format_exc().splitlines()[-1])
        else:
            warn('live', '결제 기간이 없어 실제 계산 테스트 스킵')
    else:
        warn('live', '결제 설정(payment_cycle+weekly_fee) 완료된 enrollment 없음 — 청구서 생성 테스트 불가')

    # 미분류 pending_review 조정 건수
    review_count = SessionAdjustment.get_pending_review_count()
    if review_count > 0:
        warn('live', f'분류 대기 인정결석 {review_count}건 있음 → 관리자 분류 필요')
    else:
        ok('live', '분류 대기 인정결석 없음')

    # 미발송 SMS 청구서
    unsent = Payment.query.filter_by(
        payment_type='tuition', status='pending'
    ).filter(Payment.sms_sent_at.is_(None)).count()
    ok('live', f'문자 미발송 pending 청구서: {unsent}건')

except Exception as e:
    fail('live', f'결합 테스트 오류: {e}', traceback.format_exc().splitlines()[-1])


# ════════════════════════════════════════════════════════
# 최종 결과 요약
# ════════════════════════════════════════════════════════
print(f'\n{"═"*55}')
print('  최종 테스트 결과 요약')
print(f'{"═"*55}')

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
warned = sum(1 for r in results if r[0] == WARN)

print(f'  ✅ 통과: {passed}건')
print(f'  ❌ 실패: {failed}건')
print(f'  ⚠️  경고: {warned}건')

if failed > 0:
    print(f'\n  ── 실패 항목 ──')
    for r in results:
        if r[0] == FAIL:
            print(f'  {FAIL} [{r[1]}] {r[2]}')

if warned > 0:
    print(f'\n  ── 경고 항목 ──')
    for r in results:
        if r[0] == WARN:
            print(f'  {WARN} [{r[1]}] {r[2]}')

print(f'\n  {"모든 테스트 통과!" if failed == 0 else "일부 테스트 실패 — 위 항목 확인 필요"}')
print(f'{"═"*55}\n')

sys.exit(0 if failed == 0 else 1)
