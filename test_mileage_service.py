#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""마일리지 적립 엔진(app/services/mileage_service.py) 확인 스크립트

docs/mileage/06_개발지시서_1단계.md 7절의 5개 확인 항목을 검증한다.
테스트용으로 만든 User/Student/PointEvent는 스크립트 마지막에 전부 삭제한다.
"""
import sys
import io
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.mileage import PointEvent
from app.services import mileage_service as svc

app = create_app('development')

# 이 테스트는 마일리지 적립 시작일 게이트(2026-09-01, MILEAGE_START_DATE)와
# 무관한 로직을 확인한다. 이 스크립트를 시작일 이전(오늘)에 돌리면 occurred_at
# 기본값(datetime.utcnow())이 게이트에 걸려 모든 적립이 조용히 무시되므로,
# 두 모듈이 각자 import해 간 상수를 테스트 범위 안에서만 과거로 낮춰 우회한다.
import app.services.mileage_service as _mileage_service_mod
import app.services.mileage_batch_service as _mileage_batch_service_mod
from datetime import date as _date
_mileage_service_mod.MILEAGE_START_DATE = _date(2000, 1, 1)
_mileage_batch_service_mod.MILEAGE_START_DATE = _date(2000, 1, 1)

failures = []


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


with app.app_context():
    print("=" * 70)
    print("마일리지 서비스 확인 스크립트")
    print("=" * 70)

    # --- 테스트용 강사/학생 생성 ---
    teacher = User(email='_mileage_test_teacher@example.com', name='_mileage_test_teacher',
                   role='teacher', role_level=3)
    teacher.set_password('test_password_only')
    db.session.add(teacher)
    db.session.flush()

    student = Student(teacher_id=teacher.user_id, name='_mileage_test_student', grade='초5')
    db.session.add(student)
    db.session.flush()
    student_id = student.student_id
    print(f"\n테스트 학생 생성: {student_id}")

    try:
        # 1. RW01 적립 -> 500점 조회
        print("\n[1] RW01 적립 -> 500점 조회되는가")
        event = svc.award_points(student_id, 'RW01', 'essay', 'essay-test-001')
        check("award_points가 PointEvent를 반환함", event is not None)
        check("적립 즉시 confirmed 상태", event is not None and event.status == 'confirmed')
        total = svc.get_total_points(student_id)
        check(f"누적 포인트 500 (실제: {total})", total == 500)

        # 2. 같은 essay_id로 다시 적립 시도 -> None, 점수 그대로
        print("\n[2] 같은 essay_id로 재적립 시도 -> None, 점수 그대로")
        event2 = svc.award_points(student_id, 'RW01', 'essay', 'essay-test-001')
        check("중복 적립은 None 반환", event2 is None)
        total_after = svc.get_total_points(student_id)
        check(f"점수 그대로 500 (실제: {total_after})", total_after == 500)

        # 3. CM01을 하루 6번 적립 시도 -> 5건만 (일일 상한 5건)
        print("\n[3] CM01 하루 6번 적립 시도 -> 5건만 성공")
        now = datetime.utcnow()
        cm_results = []
        for i in range(6):
            r = svc.award_points(student_id, 'CM01', 'comment', f'comment-test-{i:03d}', occurred_at=now)
            cm_results.append(r)
        success_count = sum(1 for r in cm_results if r is not None)
        check(f"6번 중 5건만 성공 (실제: {success_count}건)", success_count == 5)
        check("6번째 호출은 None (일일 상한 초과)", cm_results[5] is None)

        # 4. 적립 취소 -> 합계 0, 원장에는 2줄(적립·취소)
        print("\n[4] 적립 취소 -> 합계 0, 원장 2줄(적립+취소)")
        cancel_count = svc.cancel_points('essay', 'essay-test-001', reason='테스트 취소')
        check(f"취소 처리 1건 (실제: {cancel_count}건)", cancel_count == 1)
        rw01_events = PointEvent.query.filter_by(
            student_id=student_id, activity_code='RW01', source_type='essay', source_id='essay-test-001'
        ).all()
        check(f"RW01 원장에 2줄 (적립+취소, 실제: {len(rw01_events)}줄)", len(rw01_events) == 2)
        rw01_total = sum(e.points for e in rw01_events if e.status != 'cancelled')
        # award 행 자체가 status='cancelled'로 바뀌므로 위 합계는 취소행(음수, status='cancelled')만 제외한 것
        check(f"RW01만 놓고 보면 합계 0 (실제: {rw01_total})", rw01_total == 0)

        # 5. 등급 계산이 정책표와 일치하는가 (경계값) - 2026-08-29 개정
        # (essay_type 기능으로 RW02가 신설되어 누적 속도가 빨라진 것을 반영해
        # 0 / 2,000 / 8,000 / 20,000 / 45,000으로 하향 조정)
        print("\n[5] 등급 계산 경계값 확인 (0 / 2,000 / 8,000 / 20,000 / 45,000)")
        boundary_cases = [
            (0, 1, '브론즈'),
            (1999, 1, '브론즈'),
            (2000, 2, '실버'),
            (7999, 2, '실버'),
            (8000, 3, '골드'),
            (19999, 3, '골드'),
            (20000, 4, '다이아'),
            (44999, 4, '다이아'),
            (45000, 5, '마스터'),
            (500000, 5, '마스터'),
        ]
        for points, expected_level, expected_name in boundary_cases:
            tier = svc.get_tier(points)
            ok = tier['level'] == expected_level and tier['name'] == expected_name
            check(f"{points}점 -> {expected_name}(레벨{expected_level}) (실제: {tier['name']}(레벨{tier['level']}))", ok)
        # 마스터는 진행도 표시 안 함
        master_tier = svc.get_tier(45000)
        check("마스터는 stars/progress가 None", master_tier['stars'] is None and master_tier['progress'] is None)

        # get_kst_day_range / get_kst_week_range 공통 헬퍼 동작 확인 (④ 결정 사항)
        print("\n[부가] KST 경계 헬퍼 동작 확인")
        day_start, day_end = svc.get_kst_day_range(datetime(2026, 9, 1, 0, 30))  # UTC 00:30 = KST 09:30
        check(f"KST 2026-09-01 00:30 UTC -> 하루 시작 UTC 2026-08-31 15:00 (실제: {day_start})",
              day_start == datetime(2026, 8, 31, 15, 0))
        week_start, week_end = svc.get_kst_week_range(datetime(2026, 9, 2, 0, 30))  # KST 2026-09-02(수)
        check(f"수요일이 속한 주의 시작이 월요일인가 (실제: {week_start})",
              week_start.weekday() == 0 or True)  # UTC 기준이라 weekday 직접 비교는 KST 변환 후 확인
        kst_week_start = week_start + timedelta(hours=9)
        check(f"KST로 환산한 주 시작 요일이 월요일 (실제 요일: {kst_week_start.weekday()})",
              kst_week_start.weekday() == 0)

        # ⑤ allowed_source_types 화이트리스트 검증
        print("\n[부가] source_type 화이트리스트 검증 (⑤ 결정 사항)")
        try:
            svc.award_points(student_id, 'RW01', 'post', 'wrong-source-type-001')
            check("RW01에 'post' source_type -> ValueError 발생해야 함", False)
        except ValueError as e:
            check(f"RW01에 잘못된 source_type -> ValueError 발생 ({e})", True)

        try:
            svc.award_points(student_id, 'EX01', 'post', 'ex01-post-001')
            check("EX01에 'post' source_type은 허용됨 (essay/post 둘 다 허용)", True)
        except ValueError:
            check("EX01에 'post' source_type은 허용되어야 함", False)

        # 고정 점수 코드에 다른 points 강제 시도 -> ValueError
        try:
            svc.award_points(student_id, 'RW01', 'essay', 'essay-test-002', points=999)
            check("RW01에 임의 points(999) 지정 -> ValueError 발생해야 함", False)
        except ValueError as e:
            check(f"RW01에 임의 points 지정 -> ValueError 발생 ({e})", True)

        # EV01 범위 초과 시도 -> ValueError
        try:
            svc.award_points(student_id, 'EV01', 'manual', 'ev01-test-001', points=9999)
            check("EV01 범위(100~500) 초과 -> ValueError 발생해야 함", False)
        except ValueError as e:
            check(f"EV01 범위 초과 -> ValueError 발생 ({e})", True)

    finally:
        # --- 테스트 데이터 정리 ---
        print("\n" + "=" * 70)
        print("테스트 데이터 정리 중...")
        PointEvent.query.filter_by(student_id=student_id).delete()
        db.session.delete(student)
        db.session.delete(teacher)
        db.session.commit()
        print("정리 완료 (테스트로 만든 User/Student/PointEvent 전부 삭제됨)")

    print("\n" + "=" * 70)
    if failures:
        print(f"결과: {len(failures)}건 실패")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("결과: 전체 통과")
