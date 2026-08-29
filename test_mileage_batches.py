#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""3단계(배치 작업·뱃지 엔진) 확인 스크립트

로컬 DB에 학생/수업/출결 실데이터가 없어(0건) 이 스크립트가 직접 합성
데이터를 만들어 검증한다. 테스트로 만든 데이터는 스크립트 마지막에 전부
삭제한다.
"""
import sys
import io
from datetime import date, datetime, timedelta

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.course import Course, CourseEnrollment, CourseSession
from app.models.attendance import Attendance
from app.models.makeup_request import MakeupClassRequest
from app.models.payment_period import PaymentPeriod
from app.models.community import Post, Comment, PostLike
from app.models.essay import Essay
from app.models.mileage import PointEvent, Badge, StudentBadge, MonthlyRanking, MileageConsent
from app.models.notification import Notification
from app.services import mileage_service as svc
from app.services import mileage_batch_service as batch_svc
from app.services import ranking_service as rank_svc
from app.services import badge_service as badge_svc

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
created = {'users': [], 'students': [], 'courses': [], 'posts': [], 'essays': []}


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


def make_user(email, name, role='student', role_level=6):
    u = User(email=email, name=name, role=role, role_level=role_level)
    u.set_password('test_password_only')
    db.session.add(u)
    db.session.flush()
    created['users'].append(u.user_id)
    return u


def make_student(teacher_id, name, grade, user_id=None):
    s = Student(teacher_id=teacher_id, name=name, grade=grade, user_id=user_id)
    db.session.add(s)
    db.session.flush()
    created['students'].append(s.student_id)
    return s


def make_course(teacher_id, name, code, weekday=0, course_type='정규반'):
    c = Course(course_name=name, course_code=code, teacher_id=teacher_id,
              weekday=weekday, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
              course_type=course_type)
    db.session.add(c)
    db.session.flush()
    created['courses'].append(c.course_id)
    return c


def make_session(course_id, number, session_date, status='completed'):
    s = CourseSession(course_id=course_id, session_number=number, session_date=session_date, status=status)
    db.session.add(s)
    db.session.flush()
    return s


def make_enrollment(course_id, student_id, enrolled_at=None):
    e = CourseEnrollment(course_id=course_id, student_id=student_id,
                         enrolled_at=enrolled_at or datetime(2026, 1, 1))
    db.session.add(e)
    db.session.flush()
    return e


def make_attendance(session_id, student_id, enrollment_id, status):
    a = Attendance(session_id=session_id, student_id=student_id, enrollment_id=enrollment_id, status=status)
    db.session.add(a)
    db.session.flush()
    return a


with app.app_context():
    print("=" * 70)
    print("3단계 배치/뱃지 확인 스크립트")
    print("=" * 70)

    teacher = make_user('_batch_test_teacher@example.com', '_batch_teacher', 'teacher', 3)

    try:
        # ============================================================
        # 1. AT01 주간 출석 배치
        # ============================================================
        print("\n[1] AT01 - 예정된 세션 전부 출석 시 지급")
        studentA = make_student(teacher.user_id, '_batch_studentA', '초3')
        studentB = make_student(teacher.user_id, '_batch_studentB', '초3')
        courseW = make_course(teacher.user_id, '_배치테스트 수업W', 'BATCH-W-001', weekday=0)

        target_monday = date(2026, 8, 3)  # 임의의 월요일
        target_wed = target_monday + timedelta(days=2)

        sess1 = make_session(courseW.course_id, 1, target_monday)
        sess2 = make_session(courseW.course_id, 2, target_wed)

        enrA = make_enrollment(courseW.course_id, studentA.student_id)
        enrB = make_enrollment(courseW.course_id, studentB.student_id)

        make_attendance(sess1.session_id, studentA.student_id, enrA.enrollment_id, 'present')
        make_attendance(sess2.session_id, studentA.student_id, enrA.enrollment_id, 'late')
        make_attendance(sess1.session_id, studentB.student_id, enrB.enrollment_id, 'present')
        make_attendance(sess2.session_id, studentB.student_id, enrB.enrollment_id, 'absent')

        dry_results = batch_svc.run_weekly_attendance_batch(monday=target_monday, dry_run=True)
        by_student = {r['student_id']: r for r in dry_results}
        check("studentA dry-run: would_award", by_student[studentA.student_id]['action'].startswith('would_award'))
        check("studentB dry-run: not_eligible", by_student[studentB.student_id]['action'].startswith('not_eligible'))
        check(f"studentA scheduled=2 attended=2 (실제: {by_student[studentA.student_id]['scheduled_count']}/{by_student[studentA.student_id]['attended_count']})",
              by_student[studentA.student_id]['scheduled_count'] == 2 and by_student[studentA.student_id]['attended_count'] == 2)

        real_results = batch_svc.run_weekly_attendance_batch(monday=target_monday, dry_run=False)
        by_student2 = {r['student_id']: r for r in real_results}
        check("studentA 실제 실행: awarded", by_student2[studentA.student_id]['action'].startswith('awarded'))
        check(f"studentA AT01 100점 (실제: {svc.get_total_points(studentA.student_id)})",
              svc.get_total_points(studentA.student_id) == 100)
        check(f"studentB 포인트 없음 (실제: {svc.get_total_points(studentB.student_id)})",
              svc.get_total_points(studentB.student_id) == 0)

        # 재실행 시 중복 지급 없는지
        rerun = batch_svc.run_weekly_attendance_batch(monday=target_monday, dry_run=False)
        by_student3 = {r['student_id']: r for r in rerun}
        check("재실행 시 studentA: skip(이미 지급됨)", 'skip' in by_student3[studentA.student_id]['action'])
        check(f"재실행 후에도 100점 그대로 (실제: {svc.get_total_points(studentA.student_id)})",
              svc.get_total_points(studentA.student_id) == 100)

        # ============================================================
        # 2. AT02 분기 완주 배치
        # ============================================================
        print("\n[2] AT02 - PaymentPeriod 기준 분기 완주 판정 (엄격한 보강 인정)")
        period = PaymentPeriod(period_type='quarterly', year=2026, period_number=2,
                               label='2026년 2분기 테스트', start_date=date(2026, 3, 2),
                               end_date=date(2026, 5, 24), weeks_count=12)
        db.session.add(period)
        db.session.flush()

        courseQ = make_course(teacher.user_id, '_배치테스트 수업Q', 'BATCH-Q-001', weekday=1)
        enrA_q = make_enrollment(courseQ.course_id, studentA.student_id, enrolled_at=datetime(2026, 1, 1))
        enrB_q = make_enrollment(courseQ.course_id, studentB.student_id, enrolled_at=datetime(2026, 1, 1))
        # 분기 도중 등록한 학생(studentC)
        studentC = make_student(teacher.user_id, '_batch_studentC', '초3')
        enrC_q = make_enrollment(courseQ.course_id, studentC.student_id, enrolled_at=datetime(2026, 4, 1))

        q_sessions = []
        for i, d in enumerate([date(2026, 3, 3), date(2026, 3, 10), date(2026, 3, 17)], start=1):
            s = make_session(courseQ.course_id, i, d)
            q_sessions.append(s)

        # studentA: 3회 전부 출석 -> 결석 0
        for s in q_sessions:
            make_attendance(s.session_id, studentA.student_id, enrA_q.enrollment_id, 'present')

        # studentB: 1회 결석, 보강으로 실제 출석 -> effective_absent 0이어야 함(엄격 기준)
        make_attendance(q_sessions[0].session_id, studentB.student_id, enrB_q.enrollment_id, 'present')
        make_attendance(q_sessions[1].session_id, studentB.student_id, enrB_q.enrollment_id, 'absent')
        make_attendance(q_sessions[2].session_id, studentB.student_id, enrB_q.enrollment_id, 'present')

        makeup_course = make_course(teacher.user_id, '_배치테스트 보강', 'BATCH-MK-001', weekday=2,
                                   course_type='보강수업')
        makeup_session = make_session(makeup_course.course_id, 1, date(2026, 3, 12))
        makeup_enrollment = make_enrollment(makeup_course.course_id, studentB.student_id)
        make_attendance(makeup_session.session_id, studentB.student_id, makeup_enrollment.enrollment_id, 'present')

        makeup_request = MakeupClassRequest(
            student_id=studentB.student_id, requested_course_id=makeup_course.course_id,
            original_course_id=courseQ.course_id, status='approved',
            created_makeup_course_id=makeup_course.course_id,
        )
        db.session.add(makeup_request)
        db.session.flush()

        # studentC: 분기 도중 등록 -> 대상 제외
        for s in q_sessions:
            make_attendance(s.session_id, studentC.student_id, enrC_q.enrollment_id, 'present')

        q_dry = batch_svc.run_quarterly_completion_batch(year=2026, period_number=2, dry_run=True)
        q_by_student = {r['student_id']: r for r in q_dry}

        check(f"studentA 결석 0 -> would_award (실제: {q_by_student[studentA.student_id]['action']})",
              q_by_student[studentA.student_id]['action'].startswith('would_award'))
        check(f"studentB 결석 1건, 보강 출석 1건 -> effective_absent=0, would_award (실제: {q_by_student[studentB.student_id]})",
              q_by_student[studentB.student_id]['effective_absent'] == 0
              and q_by_student[studentB.student_id]['action'].startswith('would_award'))
        check("studentC(분기 도중 등록)는 대상에서 제외됨", studentC.student_id not in q_by_student)

        q_real = batch_svc.run_quarterly_completion_batch(year=2026, period_number=2, dry_run=False)
        check(f"studentA AT02 1000점 (실제: {svc.get_total_points(studentA.student_id)})",
              svc.get_total_points(studentA.student_id) == 1100)  # AT01(100) + AT02(1000)
        check(f"studentB AT02 1000점 (보강 인정, 실제: {svc.get_total_points(studentB.student_id)})",
              svc.get_total_points(studentB.student_id) == 1000)

        # 보강 출석이 없는 케이스 비교용 - 결석은 있지만 보강을 안 다닌 학생
        studentD = make_student(teacher.user_id, '_batch_studentD', '초3')
        enrD_q = make_enrollment(courseQ.course_id, studentD.student_id, enrolled_at=datetime(2026, 1, 1))
        make_attendance(q_sessions[0].session_id, studentD.student_id, enrD_q.enrollment_id, 'present')
        make_attendance(q_sessions[1].session_id, studentD.student_id, enrD_q.enrollment_id, 'absent')
        make_attendance(q_sessions[2].session_id, studentD.student_id, enrD_q.enrollment_id, 'present')
        # SessionAdjustment로 결제 반영은 됐지만(관대한 기준이면 통과) 실제 보강 출석은 없음
        from app.models.session_adjustment import SessionAdjustment
        sa = SessionAdjustment(student_id=studentD.student_id, enrollment_id=enrD_q.enrollment_id,
                               adjustment_type='rollover', sessions_count=1, source='teacher_excused',
                               status='applied')
        db.session.add(sa)
        db.session.flush()

        q_dry2 = batch_svc.run_quarterly_completion_batch(year=2026, period_number=2, dry_run=True)
        q_by_student2 = {r['student_id']: r for r in q_dry2}
        check(f"studentD: 결제 반영(SessionAdjustment)만 있고 보강 미출석 -> not_eligible (엄격 기준, 실제: {q_by_student2[studentD.student_id]['action']})",
              q_by_student2[studentD.student_id]['action'].startswith('not_eligible'))

        # ============================================================
        # 3. 월간 랭킹
        # ============================================================
        print("\n[3] 월간 랭킹 - 밴드 그룹핑 + 동점 처리 + 동의 익명화")
        season = '2026-08'
        studentE = make_student(teacher.user_id, '_batch_studentE', '고1')  # 다른 밴드

        # studentA, studentB 둘 다 이번엔 같은 시즌에 동일 점수를 만들고 EX01 건수로 동점 처리
        now = datetime.utcnow()
        pe1 = PointEvent(student_id=studentA.student_id, activity_code='EV01', entry_type='award',
                         points=300, status='confirmed', source_type='manual', source_id='rank-test-A',
                         season=season, occurred_at=now, confirmed_at=now)
        pe2 = PointEvent(student_id=studentB.student_id, activity_code='EV01', entry_type='award',
                         points=300, status='confirmed', source_type='manual', source_id='rank-test-B',
                         season=season, occurred_at=now, confirmed_at=now)
        pe3_ex01 = PointEvent(student_id=studentA.student_id, activity_code='EX01', entry_type='award',
                              points=1000, status='confirmed', source_type='essay', source_id='rank-ex01-A',
                              season=season, occurred_at=now, confirmed_at=now)
        pe4 = PointEvent(student_id=studentE.student_id, activity_code='EV01', entry_type='award',
                         points=200, status='confirmed', source_type='manual', source_id='rank-test-E',
                         season=season, occurred_at=now, confirmed_at=now)
        db.session.add_all([pe1, pe2, pe3_ex01, pe4])
        db.session.flush()

        consent = MileageConsent(student_id=studentB.student_id, consent_type='A', is_agreed=False,
                                 agreed_by_user_id=teacher.user_id, agreed_by_relation='self',
                                 doc_version='v1', agreed_at=now)
        db.session.add(consent)
        db.session.flush()

        live = rank_svc.build_ranking(season, finalize=False)
        elem_group = [e for e in live if e['level_group'] == 'elem34']
        high_group = [e for e in live if e['level_group'] == 'high']

        check(f"elem34 그룹에 studentA, studentB 2명 (실제: {len(elem_group)}명)", len(elem_group) == 2)
        check(f"high 그룹에 studentE 1명 (실제: {len(high_group)}명)", len(high_group) == 1)
        # studentA(EX01 1건)가 studentB(EX01 0건)보다 동점에서 1위여야 함(점수는 둘 다 300 - EV01만 기준으로 계산했지만
        # 실제로 studentA는 EX01(1000점)도 있어 점수 자체가 이미 더 높음 - 점수 우선순위 확인용으로 재구성)
        elem_sorted = sorted(elem_group, key=lambda e: e['rank'])
        check(f"1위가 studentA (점수가 더 높음, 실제 1위: {elem_sorted[0]['student_id'] == studentA.student_id})",
              elem_sorted[0]['student_id'] == studentA.student_id)
        studentB_entry = next(e for e in elem_group if e['student_id'] == studentB.student_id)
        check(f"studentB는 비동의라 anonymous=True (실제: {studentB_entry['anonymous']})",
              studentB_entry['anonymous'] is True)
        studentA_entry = next(e for e in elem_group if e['student_id'] == studentA.student_id)
        check(f"studentA는 동의 기록 없어 기본값 anonymous=True (실제: {studentA_entry['anonymous']})",
              studentA_entry['anonymous'] is True)

        # 저장(1일차 잠정) -> 확정(3일차)
        rank_svc.build_ranking(season, finalize=True, is_final=False)
        db.session.flush()
        saved_provisional = MonthlyRanking.query.filter_by(season=season, level_group='elem34').all()
        check(f"잠정 저장 후 is_final=False (실제: {[r.is_final for r in saved_provisional]})",
              all(r.is_final is False for r in saved_provisional))

        rank_svc.build_ranking(season, finalize=True, is_final=True)
        db.session.flush()
        fetched = rank_svc.get_ranking(season, level_group='elem34')
        check(f"확정 후 get_ranking이 is_final=True 스냅샷 반환 (실제: {[r['is_final'] for r in fetched]})",
              all(r['is_final'] for r in fetched))

        # ============================================================
        # 4. 뱃지 엔진
        # ============================================================
        print("\n[4] 뱃지 엔진 - first_event / external_metric / count_threshold / all_badges")
        student_owner_user = make_user('_batch_owner@example.com', '_batch_owner_user', 'student', 6)
        studentF = make_student(teacher.user_id, '_batch_studentF', '초3', user_id=student_owner_user.user_id)
        liker_user = make_user('_batch_liker@example.com', '_batch_liker', 'student', 6)
        parent_user = make_user('_batch_parent@example.com', '_batch_parent', 'parent', 5)
        db.session.add(ParentStudent(parent_id=parent_user.user_id, student_id=studentF.student_id,
                                     relation_type='parent', permission_level='full', is_active=True))
        db.session.flush()

        # BG01(첫 문장)/BG03(첫 고쳐쓰기) - 2026-08-29 개정으로 point_events가
        # 아니라 essays 테이블을 직접 본다. 리라이팅 유형 과제 하나면 둘 다
        # 동시에 충족된다(BG01은 유형 무관, BG03은 essay_type='rewriting').
        post_f = Post(user_id=student_owner_user.user_id, title='_batch_post', content='내용', category='free')
        db.session.add(post_f)
        db.session.flush()
        created['posts'].append(post_f.post_id)

        essay_f = Essay(student_id=studentF.student_id, user_id=teacher.user_id,
                        title='_batch_essay', original_text='내용', grade='초3',
                        essay_type='rewriting')
        db.session.add(essay_f)
        db.session.flush()
        created['essays'].append(essay_f.essay_id)

        granted1 = badge_svc.evaluate_badges(studentF.student_id, trigger_codes=['essay'])
        granted_codes = {(g.badge_code if hasattr(g, 'badge_code') else g.get('badge_code')) for g in granted1}
        check(f"BG01(과제 제출) 획득 (실제 부여: {granted_codes})", 'BG01' in granted_codes)
        check(f"BG03(리라이팅) 획득 (실제 부여: {granted_codes})", 'BG03' in granted_codes)

        notif_count_student = Notification.query.filter_by(user_id=student_owner_user.user_id).count()
        notif_count_parent = Notification.query.filter_by(user_id=parent_user.user_id).count()
        check(f"학생에게 뱃지 알림 발송됨 (실제: {notif_count_student}건)", notif_count_student >= 1)
        check(f"학부모에게도 뱃지 알림 발송됨 (실제: {notif_count_parent}건)", notif_count_parent >= 1)

        # BG07(받은 좋아요) - 2026-08-29 개정으로 임계치 100->30, 마일리지
        # 시작일(2026-09-01, KST) 이후 좋아요만 집계한다. 25개만 만들고
        # 미달 확인 -> 그 다음 5개 더 채워(합 30개) 충족 확인.
        gate_dt = datetime(2026, 9, 10)  # 시작일 이후 - 게이트 통과용
        for i in range(25):
            db.session.add(PostLike(user_id=f'_batch_fake_liker_{i}', post_id=post_f.post_id,
                                    created_at=gate_dt))
        db.session.flush()
        # 존재하지 않는 user_id를 써서 FK 제약이 없는 로컬 sqlite 특성을 이용한 카운트
        # 전용 더미이므로, 실제 집계 쿼리(PostLike join Post)가 이 값을 정확히 세는지만 확인한다.
        under_threshold = badge_svc._received_likes_count(studentF)
        check(f"좋아요 25개 집계됨 (실제: {under_threshold})", under_threshold == 25)
        granted_partial = badge_svc.evaluate_badges(studentF.student_id, trigger_codes=['BG07'])
        granted_codes_partial = {(g.badge_code if hasattr(g, 'badge_code') else g.get('badge_code')) for g in granted_partial}
        check("좋아요 25개(임계치 30 미달) -> BG07 아직 미획득", 'BG07' not in granted_codes_partial)

        for i in range(25, 30):
            db.session.add(PostLike(user_id=f'_batch_fake_liker_{i}', post_id=post_f.post_id,
                                    created_at=gate_dt))
        db.session.flush()
        granted3 = badge_svc.evaluate_badges(studentF.student_id, trigger_codes=['BG07'])
        granted_codes3 = {(g.badge_code if hasattr(g, 'badge_code') else g.get('badge_code')) for g in granted3}
        check(f"좋아요 30개 달성 -> BG07 획득 (실제 부여: {granted_codes3})", 'BG07' in granted_codes3)

        # 시작일 이전 좋아요는 집계에서 빠지는지 확인 (게이트 확인)
        pre_gate_liker = f'_batch_fake_liker_pregate'
        db.session.add(PostLike(user_id=pre_gate_liker, post_id=post_f.post_id,
                                created_at=datetime(2026, 8, 20)))
        db.session.flush()
        still_30 = badge_svc._received_likes_count(studentF)
        check(f"시작일 이전 좋아요는 집계에서 제외됨 (실제: {still_30})", still_30 == 30)

        # BG02, BG04, BG05, BG06, BG09 - 남은 뱃지 강제 충족시키기(BG10 확인용)
        svc.award_points(student_id=studentF.student_id, activity_code='QS01',
                         source_type='post', source_id='batch-post-F')
        svc.confirm_pending_points(now=datetime.utcnow() + timedelta(hours=25))
        svc.award_points(student_id=studentF.student_id, activity_code='EX01',
                         source_type='essay', source_id='batch-ex01-F')
        svc.award_points(student_id=studentF.student_id, activity_code='QS02',
                         source_type='post', source_id='batch-qs02-F')
        # AT02를 1건만 주면 BG06(first_event)은 충족되지만 BG08(count_threshold=4)은
        # 미달이어야 정상 - 먼저 그 상태를 확인한다.
        svc.award_points(student_id=studentF.student_id, activity_code='AT02',
                         source_type='attendance_quarter', source_id='batch-at02-F-1')
        badge_svc.evaluate_badges(studentF.student_id, trigger_codes=['AT02'])
        owned_after_1 = {sb.badge_code for sb in StudentBadge.query.filter_by(student_id=studentF.student_id).all()}
        check(f"AT02 1건 -> BG06(첫 완주)은 획득 (실제: {'BG06' in owned_after_1})", 'BG06' in owned_after_1)
        check(f"AT02 1건 -> BG08(4분기 임계치)은 아직 미획득 (실제: {'BG08' not in owned_after_1})",
              'BG08' not in owned_after_1)

        # BG08 충족을 위해 AT02를 3건 더(합 4건) 지급
        for i in range(2, 5):
            svc.award_points(student_id=studentF.student_id, activity_code='AT02',
                             source_type='attendance_quarter', source_id=f'batch-at02-F-{i}')
        badge_svc.grant_badge(studentF.student_id, 'BG09', granted_by=teacher.user_id)  # manual

        badge_svc.evaluate_badges(studentF.student_id)
        owned_final = {sb.badge_code for sb in StudentBadge.query.filter_by(student_id=studentF.student_id).all()}
        check(f"BG01~BG09 전부 보유 (실제: {sorted(owned_final)})",
              {'BG01', 'BG02', 'BG03', 'BG04', 'BG05', 'BG06', 'BG07', 'BG08', 'BG09'} <= owned_final)
        check(f"BG01~09 전부 채워지면 BG10(책장의 주인)도 자동 부여 (실제: {'BG10' in owned_final})",
              'BG10' in owned_final)

    finally:
        print("\n" + "=" * 70)
        print("테스트 데이터 정리 중...")

        Essay.query.filter(Essay.essay_id.in_(created['essays'])).delete(synchronize_session=False)
        PointEvent.query.filter(PointEvent.student_id.in_(created['students'])).delete(synchronize_session=False)
        StudentBadge.query.filter(StudentBadge.student_id.in_(created['students'])).delete(synchronize_session=False)
        MonthlyRanking.query.filter(MonthlyRanking.student_id.in_(created['students'])).delete(synchronize_session=False)
        MileageConsent.query.filter(MileageConsent.student_id.in_(created['students'])).delete(synchronize_session=False)
        Notification.query.filter(Notification.user_id.in_(created['users'])).delete(synchronize_session=False)
        for pid in created['posts']:
            PostLike.query.filter_by(post_id=pid).delete(synchronize_session=False)
            Comment.query.filter_by(post_id=pid).delete(synchronize_session=False)
        Post.query.filter(Post.post_id.in_(created['posts'])).delete(synchronize_session=False)
        MakeupClassRequest.query.filter(MakeupClassRequest.student_id.in_(created['students'])).delete(synchronize_session=False)
        from app.models.session_adjustment import SessionAdjustment as SA
        SA.query.filter(SA.student_id.in_(created['students'])).delete(synchronize_session=False)
        Attendance.query.filter(Attendance.student_id.in_(created['students'])).delete(synchronize_session=False)
        CourseEnrollment.query.filter(CourseEnrollment.student_id.in_(created['students'])).delete(synchronize_session=False)
        CourseSession.query.filter(CourseSession.course_id.in_(created['courses'])).delete(synchronize_session=False)
        Course.query.filter(Course.course_id.in_(created['courses'])).delete(synchronize_session=False)
        PaymentPeriod.query.filter_by(year=2026, period_number=2, label='2026년 2분기 테스트').delete(synchronize_session=False)
        ParentStudent.query.filter(ParentStudent.student_id.in_(created['students'])).delete(synchronize_session=False)
        Student.query.filter(Student.student_id.in_(created['students'])).delete(synchronize_session=False)
        User.query.filter(User.user_id.in_(created['users'])).delete(synchronize_session=False)
        db.session.commit()
        print("정리 완료")

    print("\n" + "=" * 70)
    if failures:
        print(f"결과: {len(failures)}건 실패")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("결과: 전체 통과")
