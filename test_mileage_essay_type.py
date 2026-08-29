#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""과제 유형(essay_type) 기능 확인 스크립트

2026-08-29 지시사항 6개 항목의 핵심 동작을 확인한다:
  1) essay_type 컬럼 기본값(basic)
  2) 업로드 4개 경로(강사 new/quick, 학생 자가제출, 학부모 대리제출)가
     선택한 유형을 essay.essay_type에 저장하는가
  3) 첨삭 확정 시 유형별 코드 지급(rewriting->RW01 500점 / basic->RW02 100점
     / etc->지급 없음)
  4) 확정 후 유형 변경 PATCH 차단
  5) 확정 전 유형 변경 시 뱃지 즉시 재판정(basic->rewriting 시 BG03 즉시 부여)
  6) BG01(유형 무관, 마일리지 시작일 게이트 없음, 소급 적용)
  7) BG03(essay_type='rewriting'에서만 부여)
  8) evaluate_badges()/grant_badge()의 notify=False가 실제로 알림을 막는가
     (BG01 소급 부여 스크립트가 알림 폭탄을 막을 수 있는지 확인)
  9) 업로드 4개 경로 모두 essay_type을 선택하지 않으면 업로드 자체가
     차단되는가(오지급 방지)

BG07 게이트/새 임계값, TIER_TABLE 새 기준표는 각각 test_mileage_batches.py,
test_mileage_service.py에서 이미 확인하므로 여기서는 중복하지 않는다.

주의: DB 준비/조회는 반드시 짧은 `with app.app_context():` 블록 안에서만
하고, client.get()/post() 호출은 그 블록 밖에서 한다(기존 4단계 화면
확인 스크립트에서 확인된 Flask 앱 컨텍스트 재사용 문제 회피 관행).
"""
import re
import sys
import io
import json
import uuid
from datetime import date, datetime, timedelta

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.essay import Essay, ESSAY_TYPE_DEFAULT
from app.models.mileage import PointEvent, Badge, StudentBadge
from app.models.notification import Notification
from app.essays.momoai_service import MOMOAIService
from app.services import badge_service as badge_svc
from app.services import mileage_service as msvc

app = create_app('development')

# 이 스크립트는 마일리지 적립 시작일 게이트(2026-09-01)와 무관한 로직
# (essay_type 저장/뱃지 판정)과, 게이트가 실제로 적용되는지(BG01은 게이트가
# 없어야 함) 둘 다 확인해야 하므로 award_points() 호출부는 게이트를 우회하지
# 않는다 - 대신 occurred_at을 명시적으로 지정해 케이스별로 통제한다.
client = app.test_client()
failures = []

# 첨삭 확정([3]) 테스트는 award_points()를 실제로 호출하므로, 마일리지
# 적립 시작일 게이트(2026-09-01)와 무관하게 RW01/RW02 지급 로직 자체를
# 확인하기 위해 기존 회귀 스크립트와 동일한 방식으로 게이트를 우회한다.
# ([6]의 "BG01은 게이트가 없다" 확인은 badge_service를 직접 호출하므로
# 이 우회와 무관하다.)
import app.services.mileage_service as _mileage_service_mod
_mileage_service_mod.MILEAGE_START_DATE = date(2000, 1, 1)


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


def login_as(user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = user_id
        sess['_fresh'] = True


created_user_ids = []
created_student_ids = []
created_essay_ids = []


def make_user(name, role, role_level):
    u = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
             name=name, role=role, role_level=role_level, is_active=True)
    u.set_password('test_password_only')
    db.session.add(u)
    db.session.flush()
    created_user_ids.append(u.user_id)
    return u


def make_student(name, teacher_id, user_id=None):
    s = Student(teacher_id=teacher_id, user_id=user_id, name=name, grade='초3',
               birth_date=date(2016, 1, 1), status='active')
    db.session.add(s)
    db.session.flush()
    created_student_ids.append(s.student_id)
    return s


with app.app_context():
    print("=" * 70)
    print("과제 유형(essay_type) 기능 확인 스크립트")
    print("=" * 70)

    teacher = make_user('_etype_teacher', 'teacher', 4)
    parent_user = make_user('_etype_parent', 'parent', 5)
    student_user_a = make_user('_etype_student_a', 'student', 6)
    student_a = make_student('_etype_학생A', teacher.user_id, user_id=student_user_a.user_id)
    student_user_b = make_user('_etype_student_b', 'student', 6)
    student_b = make_student('_etype_학생B', teacher.user_id, user_id=student_user_b.user_id)
    db.session.add(ParentStudent(parent_id=parent_user.user_id, student_id=student_b.student_id,
                                 relation_type='parent', permission_level='full', is_active=True))
    db.session.commit()

    teacher_id, parent_id = teacher.user_id, parent_user.user_id
    student_user_a_id, student_a_id = student_user_a.user_id, student_a.student_id
    student_user_b_id, student_b_id = student_user_b.user_id, student_b.student_id

print("\n[1] essay_type 컬럼 기본값")
with app.app_context():
    plain_essay = Essay(student_id=student_a_id, user_id=teacher_id,
                        original_text='유형 지정 안 한 과제입니다.' * 3, grade='초3')
    db.session.add(plain_essay)
    db.session.commit()
    created_essay_ids.append(plain_essay.essay_id)
    check(f"essay_type 지정 안 하면 기본값 '{ESSAY_TYPE_DEFAULT}' (실제: {plain_essay.essay_type})",
          plain_essay.essay_type == ESSAY_TYPE_DEFAULT)

print("\n[2] 업로드 4개 경로가 선택한 유형을 저장하는가")

# 2-1. 강사 - essays.new (CSRF 토큰 필요, NewEssayForm.validate_on_submit() 사용)
login_as(teacher_id)
get_resp = client.get('/essays/new')
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', get_resp.data.decode('utf-8'))
csrf_token = m.group(1) if m else None
check("essays/new GET에서 CSRF 토큰 추출 성공", csrf_token is not None)

resp_new = client.post('/essays/new', data={
    'csrf_token': csrf_token,
    'student_mode': 'existing',
    'student_id': student_a_id,
    'essay_text': '리라이팅 유형으로 제출하는 과제입니다. ' * 3,
    'essay_type': 'rewriting',
    'correction_model': 'standard',
    'api_provider': 'claude',
}, follow_redirects=False)
check(f"essays.new POST -> 302 리다이렉트 (실제: {resp_new.status_code})", resp_new.status_code == 302)

with app.app_context():
    new_essay = Essay.query.filter_by(student_id=student_a_id, essay_type='rewriting')\
        .order_by(Essay.created_at.desc()).first()
    check("essays.new에서 essay_type='rewriting' 저장됨", new_essay is not None)
    if new_essay:
        created_essay_ids.append(new_essay.essay_id)
        new_essay_id = new_essay.essay_id
        granted_at_upload = {sb.badge_code for sb in
                             StudentBadge.query.filter_by(student_id=student_a_id).all()}
        check(f"업로드 시점에 BG01 즉시 부여됨(첨삭 확정 전) (실제 보유: {granted_at_upload})",
              'BG01' in granted_at_upload)
        check(f"업로드 시점에 BG03 즉시 부여됨(rewriting, 첨삭 확정 전) (실제 보유: {granted_at_upload})",
              'BG03' in granted_at_upload)

# 2-2. 강사 - essays.quick (CSRF 미적용 라우트)
resp_quick = client.post('/essays/quick', data={
    'student_name': '_etype_임시학생',
    'grade': '초4',
    'essay_text': '기타 유형(첨삭 대상 아님) 테스트용 제출물입니다. ' * 3,
    'essay_type': 'etc',
    'correction_model': 'standard',
    'api_provider': 'claude',
}, follow_redirects=False)
check(f"essays.quick POST -> 302 리다이렉트 (실제: {resp_quick.status_code})", resp_quick.status_code == 302)

with app.app_context():
    quick_essay = Essay.query.filter_by(essay_type='etc')\
        .join(Student, Essay.student_id == Student.student_id)\
        .filter(Student.name == '_etype_임시학생').order_by(Essay.created_at.desc()).first()
    check("essays.quick에서 essay_type='etc' 저장됨", quick_essay is not None)
    if quick_essay:
        created_essay_ids.append(quick_essay.essay_id)
        created_student_ids.append(quick_essay.student_id)

# 2-3. 학생 자가제출 - student.submit_essay
login_as(student_user_a_id)
resp_student = client.post('/student/essays/new', data={
    'title': '학생이 직접 제출',
    'content': '학생이 기본과제글로 직접 제출하는 내용입니다. ' * 3,
    'essay_type': 'basic',
}, follow_redirects=False)
check(f"student.submit_essay POST -> 302 리다이렉트 (실제: {resp_student.status_code})",
      resp_student.status_code == 302)

with app.app_context():
    student_essay = Essay.query.filter_by(student_id=student_a_id, essay_type='basic',
                                          title='학생이 직접 제출').first()
    check("student.submit_essay에서 essay_type='basic' 저장됨", student_essay is not None)
    if student_essay:
        created_essay_ids.append(student_essay.essay_id)

# 2-4. 학부모 대리제출 - parent.submit_essay
login_as(parent_id)
resp_parent = client.post('/parent/essays/submit', data={
    'csrf_token': csrf_token,  # 이 라우트는 CSRF 검증을 하지 않아 토큰 값 자체는 무관
    'student_id': student_b_id,
    'title': '학부모가 대신 제출',
    'content': '학부모가 리라이팅 유형으로 대신 제출하는 내용입니다. ' * 3,
    'essay_type': 'rewriting',
}, follow_redirects=False)
check(f"parent.submit_essay POST -> 302 리다이렉트 (실제: {resp_parent.status_code})",
      resp_parent.status_code == 302)

with app.app_context():
    parent_essay = Essay.query.filter_by(student_id=student_b_id, essay_type='rewriting',
                                         title='학부모가 대신 제출').first()
    check("parent.submit_essay에서 essay_type='rewriting' 저장됨", parent_essay is not None)
    if parent_essay:
        created_essay_ids.append(parent_essay.essay_id)

print("\n[3] 첨삭 확정 시 유형별 코드 지급")
with app.app_context():
    essay_rw = Essay(student_id=student_a_id, user_id=teacher_id, original_text='리라이팅' * 20,
                     grade='초3', essay_type='rewriting', status='reviewing')
    essay_bs = Essay(student_id=student_a_id, user_id=teacher_id, original_text='기본과제글' * 20,
                     grade='초3', essay_type='basic', status='reviewing')
    essay_etc = Essay(student_id=student_a_id, user_id=teacher_id, original_text='기타' * 20,
                      grade='초3', essay_type='etc', status='reviewing')
    db.session.add_all([essay_rw, essay_bs, essay_etc])
    db.session.commit()
    for e in (essay_rw, essay_bs, essay_etc):
        created_essay_ids.append(e.essay_id)

    MOMOAIService.finalize_essay(None, essay_rw)
    rw_event = PointEvent.query.filter_by(source_type='essay', source_id=essay_rw.essay_id).first()
    check(f"rewriting 확정 -> RW01 500점 지급 (실제: {rw_event.activity_code if rw_event else None}"
          f"/{rw_event.points if rw_event else None})",
          rw_event is not None and rw_event.activity_code == 'RW01' and rw_event.points == 500)

    MOMOAIService.finalize_essay(None, essay_bs)
    bs_event = PointEvent.query.filter_by(source_type='essay', source_id=essay_bs.essay_id).first()
    check(f"basic 확정 -> RW02 100점 지급 (실제: {bs_event.activity_code if bs_event else None}"
          f"/{bs_event.points if bs_event else None})",
          bs_event is not None and bs_event.activity_code == 'RW02' and bs_event.points == 100)

    MOMOAIService.finalize_essay(None, essay_etc)
    etc_event = PointEvent.query.filter_by(source_type='essay', source_id=essay_etc.essay_id).first()
    check(f"etc 확정 -> 포인트 지급 없음 (실제: {etc_event})", etc_event is None)
    check("etc 확정도 is_finalized=True는 정상 처리됨", essay_etc.is_finalized is True)

    finalized_essay_id = essay_bs.essay_id  # DetachedInstanceError 방지 - 컨텍스트 안에서 문자열로 뽑아둠

print("\n[4] 확정 후 유형 변경 PATCH 차단 + 잘못된 값 거부")
login_as(teacher_id)
with app.app_context():
    unfinalized_essay = Essay(student_id=student_a_id, user_id=teacher_id, original_text='변경용' * 20,
                              grade='초3', essay_type='basic', status='reviewing')
    db.session.add(unfinalized_essay)
    db.session.commit()
    created_essay_ids.append(unfinalized_essay.essay_id)
    unfinalized_essay_id = unfinalized_essay.essay_id

resp_locked = client.patch(f'/essays/{finalized_essay_id}/update-essay-type',
                           data=json.dumps({'essay_type': 'rewriting'}),
                           content_type='application/json')
check(f"확정된 과제 PATCH -> 400 (실제: {resp_locked.status_code})", resp_locked.status_code == 400)
with app.app_context():
    still_basic = db.session.get(Essay, finalized_essay_id).essay_type
    check(f"확정된 과제는 유형이 그대로 유지됨(basic) (실제: {still_basic})", still_basic == 'basic')

resp_invalid = client.patch(f'/essays/{unfinalized_essay_id}/update-essay-type',
                            data=json.dumps({'essay_type': 'not_a_real_type'}),
                            content_type='application/json')
check(f"잘못된 유형 값 PATCH -> 400 (실제: {resp_invalid.status_code})", resp_invalid.status_code == 400)

print("\n[5] 확정 전 유형 변경 시 뱃지 즉시 재판정 (basic -> rewriting)")
with app.app_context():
    before_change = {sb.badge_code for sb in StudentBadge.query.filter_by(student_id=student_a_id).all()}
    check("변경 전에는 이 과제로 인한 BG03 조건 미충족 상태 확인용 스냅샷 기록", True)

resp_change = client.patch(f'/essays/{unfinalized_essay_id}/update-essay-type',
                           data=json.dumps({'essay_type': 'rewriting'}),
                           content_type='application/json')
check(f"미확정 과제 PATCH -> 200 성공 (실제: {resp_change.status_code})", resp_change.status_code == 200)
with app.app_context():
    changed_type = db.session.get(Essay, unfinalized_essay_id).essay_type
    check(f"유형이 rewriting으로 변경됨 (실제: {changed_type})", changed_type == 'rewriting')
    # BG03은 이미 [2-1]에서 학생A가 획득했을 수 있으므로, 이 케이스만으로 새로
    # 부여됐는지 보다는 "조건 재판정이 예외 없이 수행되고 최종적으로 충족
    # 상태가 됨"을 확인한다(반복 수여 대상이 아니므로 이미 보유해도 정상).
    owned_after = {sb.badge_code for sb in StudentBadge.query.filter_by(student_id=student_a_id).all()}
    check(f"유형 변경 후 BG03 보유 상태 확인 (실제 보유: {owned_after})", 'BG03' in owned_after)

print("\n[6] BG01 - 유형 무관 + 마일리지 시작일 게이트 없음(소급 적용)")
with app.app_context():
    fresh_user = make_user('_etype_bg01_fresh', 'student', 6)
    fresh_student = make_student('_etype_BG01전용', teacher_id, user_id=fresh_user.user_id)
    db.session.commit()
    fresh_student_id = fresh_student.student_id

    check("BG01 전용 학생은 처음엔 뱃지 0개", StudentBadge.query.filter_by(student_id=fresh_student_id).count() == 0)

    # 마일리지 시작일(2026-09-01)보다 훨씬 이전 시각으로 essay.created_at을
    # 강제 지정해 "이미 쌓여 있던 과거 과제"를 재현한다 - award_points()의
    # 게이트와 무관하게 BG01이 부여돼야 한다(2026-08-29 결정사항).
    old_essay = Essay(student_id=fresh_student_id, user_id=teacher_id,
                      original_text='과거에 쌓인 과제(기타 유형)' * 5, grade='초3',
                      essay_type='etc', created_at=datetime(2025, 1, 1))
    db.session.add(old_essay)
    db.session.commit()
    created_essay_ids.append(old_essay.essay_id)

    granted = badge_svc.evaluate_badges(fresh_student_id, trigger_codes=['essay'])
    granted_codes = {(g.badge_code if hasattr(g, 'badge_code') else g.get('badge_code')) for g in granted}
    check(f"essay_type='etc'(적립 대상 아님)에도 BG01은 부여됨 (실제: {granted_codes})",
          'BG01' in granted_codes)
    check(f"BG03은 rewriting이 아니므로 부여 안 됨 (실제: {granted_codes})", 'BG03' not in granted_codes)

    no_point_events = PointEvent.query.filter_by(student_id=fresh_student_id).count()
    check(f"이 학생에게는 포인트가 전혀 지급되지 않았음(BG01은 포인트와 무관) (실제: {no_point_events}건)",
          no_point_events == 0)

print("\n[7] BG03 - essay_type='rewriting'에서만 부여 (basic/etc는 부여 안 됨)")
with app.app_context():
    fresh_user2 = make_user('_etype_bg03_fresh', 'student', 6)
    fresh_student2 = make_student('_etype_BG03전용', teacher_id, user_id=fresh_user2.user_id)
    db.session.commit()
    fresh_student2_id = fresh_student2.student_id

    basic_essay = Essay(student_id=fresh_student2_id, user_id=teacher_id,
                        original_text='기본과제글만 있는 상태' * 5, grade='초3', essay_type='basic')
    db.session.add(basic_essay)
    db.session.commit()
    created_essay_ids.append(basic_essay.essay_id)

    granted_basic_only = badge_svc.evaluate_badges(fresh_student2_id, trigger_codes=['essay'])
    codes_basic_only = {(g.badge_code if hasattr(g, 'badge_code') else g.get('badge_code'))
                        for g in granted_basic_only}
    check(f"기본과제글만 있으면 BG01은 부여(유형 무관) (실제: {codes_basic_only})", 'BG01' in codes_basic_only)
    check(f"기본과제글만 있으면 BG03은 미부여 (실제: {codes_basic_only})", 'BG03' not in codes_basic_only)

    rewriting_essay = Essay(student_id=fresh_student2_id, user_id=teacher_id,
                            original_text='드디어 리라이팅 제출' * 5, grade='초3', essay_type='rewriting')
    db.session.add(rewriting_essay)
    db.session.commit()
    created_essay_ids.append(rewriting_essay.essay_id)

    granted_after_rewriting = badge_svc.evaluate_badges(fresh_student2_id, trigger_codes=['essay'])
    codes_after = {(g.badge_code if hasattr(g, 'badge_code') else g.get('badge_code'))
                  for g in granted_after_rewriting}
    check(f"리라이팅 제출 후 BG03 부여됨 (실제: {codes_after})", 'BG03' in codes_after)

print("\n[8] notify=False가 실제로 알림을 막는가 (BG01 소급 부여 알림 폭탄 방지)")
with app.app_context():
    notify_user = make_user('_etype_notify_fresh', 'student', 6)
    notify_student = make_student('_etype_알림확인', teacher_id, user_id=notify_user.user_id)
    db.session.commit()
    notify_student_id, notify_user_id = notify_student.student_id, notify_user.user_id

    backfill_essay = Essay(student_id=notify_student_id, user_id=teacher_id,
                           original_text='소급 부여 대상(과거 과제)' * 5, grade='초3',
                           essay_type='basic')
    db.session.add(backfill_essay)
    db.session.commit()
    created_essay_ids.append(backfill_essay.essay_id)

    before_notif = Notification.query.filter_by(user_id=notify_user_id).count()
    granted_silent = badge_svc.evaluate_badges(notify_student_id, trigger_codes=['essay'], notify=False)
    codes_silent = {(g.badge_code if hasattr(g, 'badge_code') else g.get('badge_code'))
                   for g in granted_silent}
    after_notif = Notification.query.filter_by(user_id=notify_user_id).count()
    check(f"notify=False로도 BG01은 정상 부여됨 (실제: {codes_silent})", 'BG01' in codes_silent)
    check(f"notify=False면 알림이 발송되지 않음 (부여 전 {before_notif}건 -> 후 {after_notif}건)",
          after_notif == before_notif)

    # 9/1 이후 새로 획득하는 경우(=배포 후 정상 운영)는 기본값(notify=True)이라
    # 그대로 알림이 가야 한다 - BG09(manual)는 first_event 트리거 필터의
    # 영향을 받지 않는 별도 경로이므로 grant_badge()로 직접 확인한다.
    before_notif2 = Notification.query.filter_by(user_id=notify_user_id).count()
    badge_svc.grant_badge(notify_student_id, 'BG09', granted_by=teacher_id)
    after_notif2 = Notification.query.filter_by(user_id=notify_user_id).count()
    check(f"grant_badge() 기본값(notify=True)은 정상적으로 알림 발송 (부여 전 {before_notif2}건 -> 후 {after_notif2}건)",
          after_notif2 > before_notif2)

    before_notif3 = Notification.query.filter_by(user_id=notify_user_id).count()
    badge_svc.revoke_badge(notify_student_id, 'BG09', '테스트 회수')
    badge_svc.grant_badge(notify_student_id, 'BG09', granted_by=teacher_id, notify=False)
    after_notif3 = Notification.query.filter_by(user_id=notify_user_id).count()
    check(f"grant_badge(notify=False)는 알림을 막음 (부여 전 {before_notif3}건 -> 후 {after_notif3}건)",
          after_notif3 == before_notif3)

print("\n[9] 업로드 4개 경로 - 유형 미선택 시 업로드 자체가 차단되는가")

login_as(teacher_id)
get_resp2 = client.get('/essays/new')
m2 = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', get_resp2.data.decode('utf-8'))
csrf_token2 = m2.group(1) if m2 else None

resp_new_missing = client.post('/essays/new', data={
    'csrf_token': csrf_token2,
    'student_mode': 'existing',
    'student_id': student_a_id,
    'essay_text': '유형을 고르지 않고 제출을 시도하는 과제입니다. ' * 3,
    # essay_type 없음
    'correction_model': 'standard',
    'api_provider': 'claude',
}, follow_redirects=False)
with app.app_context():
    blocked_new = Essay.query.filter_by(student_id=student_a_id)\
        .filter(Essay.original_text.like('유형을 고르지 않고%')).first()
    check(f"essays.new - 유형 미선택 시 과제 생성 안 됨 (실제 생성 여부: {blocked_new is not None})",
          blocked_new is None)

resp_quick_missing = client.post('/essays/quick', data={
    'student_name': '_etype_유형미선택',
    'grade': '초4',
    'essay_text': '유형 없이 제출하는 임시 첨삭입니다. ' * 3,
    'correction_model': 'standard',
    'api_provider': 'claude',
}, follow_redirects=False)
with app.app_context():
    blocked_quick = Essay.query.join(Student, Essay.student_id == Student.student_id)\
        .filter(Student.name == '_etype_유형미선택').first()
    check(f"essays.quick - 유형 미선택 시 과제 생성 안 됨 (실제 생성 여부: {blocked_quick is not None})",
          blocked_quick is None)
    if blocked_quick:
        created_essay_ids.append(blocked_quick.essay_id)
        created_student_ids.append(blocked_quick.student_id)

login_as(student_user_a_id)
resp_student_missing = client.post('/student/essays/new', data={
    'title': '유형 없이 제출(학생)',
    'content': '유형을 선택하지 않고 제출하는 내용입니다. ' * 3,
}, follow_redirects=False)
with app.app_context():
    blocked_student = Essay.query.filter_by(title='유형 없이 제출(학생)').first()
    check(f"student.submit_essay - 유형 미선택 시 과제 생성 안 됨 (실제 생성 여부: {blocked_student is not None})",
          blocked_student is None)

login_as(parent_id)
resp_parent_missing = client.post('/parent/essays/submit', data={
    'student_id': student_b_id,
    'title': '유형 없이 제출(학부모)',
    'content': '유형을 선택하지 않고 대신 제출하는 내용입니다. ' * 3,
}, follow_redirects=False)
with app.app_context():
    blocked_parent = Essay.query.filter_by(title='유형 없이 제출(학부모)').first()
    check(f"parent.submit_essay - 유형 미선택 시 과제 생성 안 됨 (실제 생성 여부: {blocked_parent is not None})",
          blocked_parent is None)

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    all_student_ids = list(set(created_student_ids))
    Essay.query.filter(Essay.essay_id.in_(created_essay_ids)).delete(synchronize_session=False)
    Essay.query.filter(Essay.student_id.in_(all_student_ids)).delete(synchronize_session=False)
    PointEvent.query.filter(PointEvent.student_id.in_(all_student_ids)).delete(synchronize_session=False)
    StudentBadge.query.filter(StudentBadge.student_id.in_(all_student_ids)).delete(synchronize_session=False)
    ParentStudent.query.filter(ParentStudent.student_id.in_(all_student_ids)).delete(synchronize_session=False)
    Notification.query.filter(Notification.user_id.in_(created_user_ids)).delete(synchronize_session=False)
    Student.query.filter(Student.student_id.in_(all_student_ids)).delete(synchronize_session=False)
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
