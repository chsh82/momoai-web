#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""월간 랭킹 실명 전환 + 공개 선택 기능 제거 확인 스크립트 (2026-08-30)

지시사항 "5. 확인" 6개 항목을 그대로 확인한다:
  1) 모든 학생이 이름과 학년으로 표시되는가
  2) 본인 행이 "나"로 강조되는가
  3) 학부모 화면에서도 동일하게 보이는가
  4) 마이페이지에 닉네임·공개 설정(A) UI가 남아 있지 않은가
  5) 공개 설정(A) 라우트에 직접 POST를 보내도 동작하지 않는가
  6) mileage_consents의 B·C 항목 동의 기능이 여전히 정상 동작하는가

주의: DB 준비/조회는 짧은 `with app.app_context():` 블록 안에서만 하고,
client.get()/post() 호출은 그 블록 밖에서 한다(기존 화면 확인 스크립트의
Flask 앱 컨텍스트 재사용 문제 회피 관행).
"""
import re
import sys
import io
import uuid
from datetime import datetime, timedelta, date

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.mileage import PointEvent, MileageConsent
from app.services import mileage_service as msvc
from app.services import ranking_service

app = create_app('development')

import app.services.mileage_service as _mileage_service_mod
_mileage_service_mod.MILEAGE_START_DATE = date(2000, 1, 1)

client = app.test_client()
failures = []


def check(label, condition):
    mark = 'PASS' if condition else 'FAIL'
    print(f"  [{mark}] {label}")
    if not condition:
        failures.append(label)


def login_as(user_id):
    with client.session_transaction() as sess:
        sess['_user_id'] = user_id
        sess['_fresh'] = True


def content_only(html):
    idx = html.find('<main')
    return html[idx:] if idx != -1 else html


created_user_ids = []
created_student_ids = []


def make_student(name, grade='초3', age=16):
    today_kst = (datetime.utcnow() + timedelta(hours=9)).date()
    birth_date = today_kst.replace(year=today_kst.year - age)
    user = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                name=name, role='student', role_level=5, is_active=True)
    user.set_password('test1234')
    db.session.add(user)
    db.session.flush()
    student = Student(teacher_id=user.user_id, user_id=user.user_id, name=name,
                      grade=grade, birth_date=birth_date, status='active')
    db.session.add(student)
    db.session.commit()
    created_user_ids.append(user.user_id)
    created_student_ids.append(student.student_id)
    return user.user_id, student.student_id


print("=" * 70)
print("월간 랭킹 실명 전환 + 공개 선택 기능 제거 확인")
print("=" * 70)

with app.app_context():
    user_x_id, student_x_id = make_student('테스트실명공개A', grade='초4')
    user_y_id, student_y_id = make_student('테스트실명공개B', grade='초4')
    parent_full_id = str(uuid.uuid4())
    parent_full = User(user_id=parent_full_id, email=f'{uuid.uuid4().hex[:8]}@test.local',
                       name='_realname_parent', role='parent', role_level=5, is_active=True)
    parent_full.set_password('test1234')
    db.session.add(parent_full)
    db.session.flush()
    created_user_ids.append(parent_full_id)
    db.session.add(ParentStudent(parent_id=parent_full_id, student_id=student_x_id,
                                 relation_type='parent', permission_level='full', is_active=True))
    db.session.commit()

    # student_x는 A항목(랭킹 공개) 비동의 기록을 일부러 남겨서, 비동의여도
    # 실명이 노출되는지 확인한다. student_y는 아예 동의 기록이 없는 상태.
    db.session.add(MileageConsent(student_id=student_x_id, consent_type='A', is_agreed=False,
                                  agreed_by_user_id=user_x_id, agreed_by_relation='self',
                                  doc_version='v1.0'))
    db.session.commit()

    now = datetime.utcnow()
    ev1 = msvc.award_points(student_x_id, 'RW01', 'essay', f'realname-{uuid.uuid4().hex[:8]}',
                            occurred_at=now)
    ev2 = msvc.award_points(student_y_id, 'QZ01', 'quiz_session', f'realname-{uuid.uuid4().hex[:8]}',
                            occurred_at=now)
    db.session.commit()

    season = msvc.get_season()

print("\n[1] 모든 학생이 이름+학년으로 표시되는가 (ranking_service 직접 호출)")
with app.app_context():
    live = ranking_service.build_ranking(season, finalize=False)
    row_x = next((r for r in live if r['student_id'] == student_x_id), None)
    row_y = next((r for r in live if r['student_id'] == student_y_id), None)
    check("student_x(A 비동의)도 실명+학년으로 표시", row_x is not None and row_x['display_name'] == '테스트실명공개A 초4')
    check("student_y(동의 기록 없음)도 실명+학년으로 표시", row_y is not None and row_y['display_name'] == '테스트실명공개B 초4')
    check("결과 딕셔너리에 anonymous 키 없음", row_x is not None and 'anonymous' not in row_x)
    check("결과 딕셔너리에 consent 키 없음", row_x is not None and 'consent' not in row_x)
    check("학교명 필드가 결과에 없음(school 키 없음)", row_x is not None and 'school' not in row_x)

print("\n[2] 본인 행이 '나'로 강조되는가 (학생 시점 랭킹 화면)")
login_as(user_x_id)
resp_self = client.get(f'/student/mileage/ranking?season={season}')
content_self = content_only(resp_self.data.decode('utf-8'))
check("응답 200", resp_self.status_code == 200)
check("본인 시점에 '나' 라벨 노출", re.search(r'>\s*나\s*<', content_self) is not None)
check("본인 이름(테스트실명공개A)은 '나'로 대체되어 본문에 없음", '테스트실명공개A' not in content_self)

login_as(user_y_id)
resp_other = client.get(f'/student/mileage/ranking?season={season}')
content_other = content_only(resp_other.data.decode('utf-8'))
check("타인 시점에서는 실명이 그대로 노출됨(테스트실명공개A)", '테스트실명공개A' in content_other)
check("'학습자' 익명 표기가 나오지 않음", '학습자' not in content_other)

print("\n[3] 학부모 화면에서도 동일하게 보이는가")
login_as(parent_full_id)
resp_parent_ranking = client.get(f'/student/mileage/ranking?season={season}&student_id={student_x_id}')
content_parent = content_only(resp_parent_ranking.data.decode('utf-8'))
check("학부모 시점 랭킹 응답 200", resp_parent_ranking.status_code == 200)
check("학부모 시점에서도 자녀 실명(테스트실명공개A)이 노출됨", '테스트실명공개A' in content_parent)
check("학부모 시점에서도 다른 학생 실명(테스트실명공개B)이 노출됨", '테스트실명공개B' in content_parent)

resp_parent_mileage = client.get(f'/parent/children/{student_x_id}/mileage')
html_parent_mileage = resp_parent_mileage.data.decode('utf-8')
check("학부모 자녀 마일리지 화면 응답 200", resp_parent_mileage.status_code == 200)

print("\n[4] 마이페이지 / 학부모 화면에 닉네임·공개 설정(A) UI가 없는가")
login_as(user_x_id)
resp_profile = client.get('/profile/')
html_profile = resp_profile.data.decode('utf-8')
check("마이페이지 응답 200", resp_profile.status_code == 200)
check("닉네임 입력 UI(placeholder) 없음", '닉네임 (2~10자)' not in html_profile)
check("닉네임 미설정 안내 배너 없음", '아직 닉네임이 없어요' not in html_profile)
check("A항목(랭킹 공개) 동의 UI 없음", '월간 랭킹에' not in html_profile and '닉네임·학년·순위·점수·뱃지 공개' not in html_profile)
check("B항목(우수답안 게시) 동의 UI는 남아있음", '우수답안의 서비스 내 게시' in html_profile)
check("C항목(홍보물 활용) 동의 UI는 남아있음", '우수답안의 홍보·교육자료 활용' in html_profile)

check("학부모 화면에도 닉네임 입력 UI 없음", '닉네임 (2~10자)' not in html_parent_mileage)
check("학부모 화면에도 닉네임 미설정 안내 배너 없음", '아직 닉네임이 없어요' not in html_parent_mileage)
check("학부모 화면에도 A항목 동의 UI 없음", '월간 랭킹 공개' not in html_parent_mileage)
check("학부모 화면에 B항목 동의 UI는 남아있음", '우수답안의 서비스 내 게시' in html_parent_mileage)

print("\n[5] 공개 설정(A) 라우트에 직접 POST를 보내도 동작하지 않는가")
with app.app_context():
    before_a = msvc.get_consent_status(student_x_id)['A']

resp_post_a_student = client.post('/profile/mileage/consent/A', data={'is_agreed': '1'}, follow_redirects=True)
check("학생 라우트로 A POST -> 200(리다이렉트 후) 응답은 오지만", resp_post_a_student.status_code == 200)
check("응답에 '잘못된 동의 항목입니다' 안내 노출", '잘못된 동의 항목입니다' in resp_post_a_student.data.decode('utf-8'))

login_as(parent_full_id)
resp_post_a_parent = client.post(f'/parent/children/{student_x_id}/mileage/consent/A',
                                 data={'is_agreed': '1'}, follow_redirects=True)
check("학부모 라우트로 A POST도 차단 안내 노출", '잘못된 동의 항목입니다' in resp_post_a_parent.data.decode('utf-8'))

with app.app_context():
    after_a = msvc.get_consent_status(student_x_id)['A']
    check(f"A 상태가 바뀌지 않음 (이전: {before_a}, 이후: {after_a})", before_a == after_a and after_a is False)

print("\n[6] mileage_consents B·C 항목 동의 기능은 정상 동작하는가")
login_as(user_x_id)
with app.app_context():
    before_b = msvc.get_consent_status(student_x_id)['B']
resp_post_b = client.post('/profile/mileage/consent/B', data={'is_agreed': '1'}, follow_redirects=True)
check("B 동의 POST 성공 응답", resp_post_b.status_code == 200)
with app.app_context():
    after_b = msvc.get_consent_status(student_x_id)['B']
    check(f"B 동의가 정상적으로 True로 바뀜 (이전: {before_b}, 이후: {after_b})",
          before_b is False and after_b is True)

login_as(parent_full_id)
with app.app_context():
    before_c = msvc.get_consent_status(student_x_id)['C']
resp_post_c = client.post(f'/parent/children/{student_x_id}/mileage/consent/C',
                          data={'is_agreed': '1'}, follow_redirects=True)
check("학부모 경로로 C 동의 POST 성공 응답", resp_post_c.status_code == 200)
with app.app_context():
    after_c = msvc.get_consent_status(student_x_id)['C']
    check(f"C 동의가 정상적으로 True로 바뀜 (이전: {before_c}, 이후: {after_c})",
          before_c is False and after_c is True)

    # mileage_consents 테이블/기존 데이터 자체는 삭제되지 않았어야 한다
    remaining_a_rows = MileageConsent.query.filter_by(student_id=student_x_id, consent_type='A').count()
    check(f"A항목 기존 이력 행은 삭제되지 않고 남아있음 (실제: {remaining_a_rows}건)", remaining_a_rows >= 1)

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    PointEvent.query.filter(PointEvent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    MileageConsent.query.filter(MileageConsent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    ParentStudent.query.filter(ParentStudent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
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
