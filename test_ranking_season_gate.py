#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""월간 랭킹 시즌 하한(RANKING_FIRST_SEASON) 게이트 확인 스크립트

배경: 마일리지 적립 시작일이 8월 31일이라 2026-08 시즌은 하루치 활동만
으로 구성된다. 이 시즌으로 순위를 생성/공개하면 안 된다 - MILEAGE_START_DATE
(포인트를 언제부터 주는지)와는 별개로, RANKING_FIRST_SEASON(2026-09, 언제부터
그 포인트로 순위를 공개하는지)이 이를 막는다.

확인 항목:
  1) build_ranking('2026-08', ...)는 데이터가 있어도 빈 리스트 반환, MonthlyRanking에
     2026-08 행이 생기지 않음
  2) build_ranking('2026-09', ...)는 정상 동작(집계·저장 모두)
  3) recent_seasons()에 '2026-08'이 없음
  4) 스케줄러 job이 8월 시즌일 때 build_ranking을 호출하지 않고 건너뜀
     (job 함수를 직접 호출해 로그로 확인 - 실제 스케줄 등록은 하지 않는다)

테스트로 만든 데이터는 스크립트 마지막에 전부 삭제한다.
"""
import sys
import io
import uuid
import logging
from datetime import datetime, date

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.mileage import PointEvent, MonthlyRanking
from app.services import mileage_service as msvc
from app.services import ranking_service
from app.services.mileage_rules import RANKING_FIRST_SEASON

app = create_app('development')
failures = []


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


created_user_ids = []
created_student_ids = []


def make_student(name):
    user = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                name=name, role='student', role_level=6, is_active=True)
    user.set_password('x')
    db.session.add(user)
    db.session.flush()
    student = Student(teacher_id=user.user_id, user_id=user.user_id, name=name,
                       grade='초3', birth_date=date(2016, 1, 1), status='active')
    db.session.add(student)
    db.session.flush()
    created_user_ids.append(user.user_id)
    created_student_ids.append(student.student_id)
    return student.student_id


with app.app_context():
    print("=" * 70)
    print("월간 랭킹 시즌 하한 게이트 확인 스크립트")
    print(f"RANKING_FIRST_SEASON = {RANKING_FIRST_SEASON}")
    print("=" * 70)

    student_id = make_student('랭킹게이트확인학생')
    # 8/31 활동 - MILEAGE_START_DATE(8/31) 게이트는 통과하지만 season은 '2026-08'
    ev_aug = msvc.award_points(student_id, 'RW01', 'essay', f'rg-aug-{uuid.uuid4().hex[:8]}',
                               occurred_at=datetime(2026, 8, 31, 0, 0, 0))
    db.session.commit()
    check("8/31 활동이 실제로 적립됨(전제 조건)", ev_aug is not None)
    check("그 적립의 season이 2026-08로 기록됨(전제 조건)", ev_aug is not None and ev_aug.season == '2026-08')

    print("\n[1] build_ranking('2026-08', ...) - 데이터가 있어도 아무것도 생성 안 함")
    results_aug = ranking_service.build_ranking('2026-08', finalize=True, is_final=False)
    db.session.commit()
    check("빈 리스트 반환", results_aug == [])
    check("MonthlyRanking에 이 학생의 2026-08 행이 생기지 않음(내 테스트 학생 기준)",
          MonthlyRanking.query.filter_by(season='2026-08', student_id=student_id).count() == 0)

    results_aug_final = ranking_service.build_ranking('2026-08', finalize=True, is_final=True)
    db.session.commit()
    check("is_final=True로 호출해도 마찬가지로 빈 리스트", results_aug_final == [])
    check("확정 시도 후에도 이 학생의 2026-08 행 없음",
          MonthlyRanking.query.filter_by(season='2026-08', student_id=student_id).count() == 0)

    print("\n[2] build_ranking('2026-09', ...) - 정상 동작")
    ev_sep = msvc.award_points(student_id, 'RW02', 'essay', f'rg-sep-{uuid.uuid4().hex[:8]}',
                               occurred_at=datetime(2026, 9, 1, 0, 0, 0))
    db.session.commit()
    check("9/1 활동도 정상 적립됨(전제 조건)", ev_sep is not None)
    check("그 적립의 season이 2026-09로 기록됨(전제 조건)", ev_sep is not None and ev_sep.season == '2026-09')

    results_sep = ranking_service.build_ranking('2026-09', finalize=True, is_final=False)
    db.session.commit()
    entry = next((r for r in results_sep if r['student_id'] == student_id), None)
    check("2026-09는 정상 집계됨(결과 존재)", entry is not None)
    check("MonthlyRanking에 2026-09 행이 정상 저장됨",
          MonthlyRanking.query.filter_by(season='2026-09', student_id=student_id).count() == 1)

    print("\n[3] recent_seasons()에 2026-08이 없음")
    seasons = ranking_service.recent_seasons(12, now=datetime(2026, 9, 5))
    check("2026-08이 목록에 없음", '2026-08' not in seasons)
    check("2026-09는 목록에 있음", '2026-09' in seasons)

    print("\n[3-1] recent_seasons() - 8/31 이전(오늘 실제 날짜) 접속 시에도 빈 목록으로 죽지 않음")
    seasons_before_start = ranking_service.recent_seasons(12, now=datetime(2026, 8, 30))
    check("목록이 비어있지 않음(seasons[0] 안전)", len(seasons_before_start) > 0)
    check("RANKING_FIRST_SEASON(2026-09)이 폴백으로 포함됨", seasons_before_start == ['2026-09'])

    print("\n[4] 스케줄러 job - 8월 시즌일 때 build_ranking 호출 없이 건너뜀")
    from unittest.mock import patch
    from app.utils import scheduler as sched

    with patch('app.services.ranking_service.previous_season', return_value='2026-08'), \
         patch('app.services.ranking_service.build_ranking') as mock_build:
        sched.ranking_monthly_provisional_job(app)
        sched.ranking_monthly_final_job(app)
    check("8월 시즌일 때 provisional/final 모두 build_ranking을 호출하지 않음",
          mock_build.call_count == 0)

    print("\n정리: 테스트 데이터 삭제")
    PointEvent.query.filter(PointEvent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    MonthlyRanking.query.filter(MonthlyRanking.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    Student.query.filter(Student.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    User.query.filter(User.user_id.in_(created_user_ids)).delete(synchronize_session=False)
    db.session.commit()
    print("  삭제 완료")

    print("\n" + "=" * 70)
    if failures:
        print(f"결과: FAIL {len(failures)}건")
        for f in failures:
            print(f"  - {f}")
    else:
        print("결과: 전체 PASS")
    print("=" * 70)
