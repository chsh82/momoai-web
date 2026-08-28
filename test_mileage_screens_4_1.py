#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""4단계 1묶음(학생 마이페이지·랭킹·공개 동의) 화면 확인 스크립트

docs/mileage/09_개발지시서_4단계.md의 1~3항목과 사용자 추가 지시 4가지를
실제 렌더링된 HTML로 확인한다(create_app() + test_client, 기존 test_*.py
관행). 테스트로 만든 User/Student/PointEvent/StudentBadge/MileageConsent는
스크립트 마지막에 전부 삭제한다.

주의: DB 준비/조회는 반드시 짧은 `with app.app_context():` 블록 안에서만
하고, client.get()/post() 호출은 그 블록 밖에서 한다. 앱 컨텍스트를 열어둔
채로 test_client 요청을 보내면 Flask가 새 요청 컨텍스트를 만들지 않고
열려 있던 컨텍스트(g)를 재사용해버려서, 로그인 사용자를 바꿔도 이전
사용자의 current_user가 그대로 남는 문제가 있었다(직접 재현해 확인함).
"""
import re
import sys
import io
import uuid
from datetime import datetime, timedelta

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.mileage import PointEvent, Badge, StudentBadge, MileageConsent
from app.services import mileage_service as msvc

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
    """base.html 사이드바/헤더(로그인한 본인 이름이 항상 나오는 영역)를 뺀
    본문(<main>...)만 돌려준다 - "랭킹에 실명이 없어야 한다" 검사는 본문
    기준이어야 한다. 사이드바의 "내 계정" 위젯은 검사 대상이 아니다."""
    idx = html.find('<main')
    return html[idx:] if idx != -1 else html


created_user_ids = []
created_student_ids = []


def make_student(name, grade='초3', nickname=None, age=16):
    """age 기본값은 16(자기 동의 가능) - 마일리지 공개 동의는 만 14세 미만이면
    본인이 아니라 학부모만 가능하므로, "본인 동의 성공" 시나리오에서 실수로
    미성년 차단에 걸리지 않도록 명시적으로 나이를 지정한다."""
    today_kst = (datetime.utcnow() + timedelta(hours=9)).date()
    birth_date = today_kst.replace(year=today_kst.year - age)

    user = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                name=name, role='student', role_level=5, is_active=True)
    user.set_password('test1234')
    db.session.add(user)
    db.session.flush()
    student = Student(teacher_id=user.user_id, user_id=user.user_id, name=name,
                       grade=grade, nickname=nickname, birth_date=birth_date, status='active')
    db.session.add(student)
    db.session.flush()
    db.session.commit()
    created_user_ids.append(user.user_id)
    created_student_ids.append(student.student_id)
    return user.user_id, student.student_id


print("=" * 70)
print("4-1 화면 확인 스크립트 (마이페이지 / 랭킹 / 공개 동의)")
print("=" * 70)

# --- [A] 신규 학생 (0점 / 뱃지 0개) - 배포 직후 상태를 다른 학생 데이터가
# 생기기 전에 먼저 확인해야 "이 학년 그룹엔 아직 아무도 없다"는 진짜 빈
# 상태를 볼 수 있다 (뒤에 B/C가 같은 학년 그룹에 점수를 만들면 더 이상
# 빈 상태가 아니게 된다).
with app.app_context():
    user_a_id, student_a_id = make_student('테스트영')

print("\n[A] 신규 학생 (0점 / 뱃지 0개) - 마이페이지·랭킹 안내문 노출 확인")
login_as(user_a_id)
resp = client.get('/profile/')
html_a = resp.data.decode('utf-8')
check("응답 200", resp.status_code == 200)
check("0점 안내 문구 노출", '이렇게 하면 점수를 받아요' in html_a)
check("적립 규칙 이름(리라이팅 제출) 노출", '리라이팅 제출' in html_a)
check("적립 내역 빈 안내 노출", '아직 적립 내역이 없어요' in html_a)
check("뱃지 수집판 잠금 상태 노출(진행도 문구)", '서비스 내 최초 게시글 작성' in html_a)

resp_r = client.get('/student/mileage/ranking')
html_ar = resp_r.data.decode('utf-8')
check("랭킹 응답 200", resp_r.status_code == 200)
check("데이터 없음 안내 노출(아직 아무도 없는 학년 그룹)", '아직 이번 달 순위가 집계되지 않았어요' in html_ar)
check("랭킹 빈 화면에서도 안내 링크 노출", '무엇을 하면 점수를 받는지' in html_ar)

# --- [B]/[C] 준비 ---
with app.app_context():
    user_b_id, student_b_id = make_student('테스트철', grade='초3', nickname='책읽는철')
    ev_confirmed = msvc.award_points(student_b_id, 'RW01', 'essay', f'essay-{uuid.uuid4().hex[:8]}')
    ev_pending = msvc.award_points(student_b_id, 'QS01', 'post', f'post-{uuid.uuid4().hex[:8]}')
    ev_to_cancel = msvc.award_points(student_b_id, 'RW01', 'essay', f'essay-{uuid.uuid4().hex[:8]}')
    db.session.flush()
    msvc.cancel_points('essay', ev_to_cancel.source_id, '중복 제출 확인되어 취소')
    for code in ('BG01', 'BG02', 'BG03'):
        db.session.add(StudentBadge(student_id=student_b_id, badge_code=code, earned_count=1))
    db.session.add(MileageConsent(student_id=student_b_id, consent_type='A', is_agreed=True,
                                  agreed_by_user_id=user_b_id, agreed_by_relation='self', doc_version='v1.0'))
    db.session.commit()

    total_b = msvc.get_total_points(student_b_id)
    pending_b = msvc.get_pending_points(student_b_id)
    check("get_pending_points가 QS01(대기) 100점만 집계", pending_b == 100)
    check("get_total_points는 확정+대기 합산(취소분 제외)", total_b == 500 + 100)

    user_c_id, student_c_id = make_student('테스트순', grade='초3', nickname='익명이될철')
    msvc.award_points(student_c_id, 'AT02', 'attendance_quarter', f'q-{uuid.uuid4().hex[:8]}', points=1000)
    db.session.commit()
    # 동의 안 함 - MileageConsent 행 자체를 만들지 않음(기본값 미동의와 동일해야 함)

    from app.services import ranking_service
    season = msvc.get_season()
    student_c_grade = db.session.get(Student, student_c_id).grade
    live = ranking_service.build_ranking(season, finalize=False)
    row_c = next((r for r in live if r['student_id'] == student_c_id), None)
    check("미동의 학생은 anonymous=True", row_c is not None and row_c['anonymous'] is True)
    check("미동의 학생 display_name이 실명이 아니라 학년 학습자 형식",
          row_c is not None and row_c['display_name'] == f'{student_c_grade} 학습자')

    user_e_id, student_e_id = make_student('테스트차단')

print("\n[B] 확정/대기/취소 혼재 + 공개 동의(A) 학생")
login_as(user_b_id)
resp_b = client.get('/profile/')
html_b = resp_b.data.decode('utf-8')
check("확정 배지 노출", '>확정<' in html_b)
check("확정 대기 배지 노출", '확정 대기' in html_b)
check("대기 포인트 별도 안내(100점 포함) 노출", '확정 대기 100점 포함' in html_b)
check("취소 배지 노출", '>취소<' in html_b)
check("취소 사유 텍스트 노출", '중복 제출 확인되어 취소' in html_b)
check("취소선(line-through) 스타일 적용", 'line-through' in html_b)
check("보유 뱃지 3개(BG01~03) 표시", '첫 문장' in html_b and '첫 물음표' in html_b and '첫 고쳐쓰기' in html_b)
check("뱃지 획득 시 컬러(초록) 스타일 적용", 'bg-green-50 border-green-300' in html_b)
check("최종 뱃지(BG10) 별도 영역 노출", '책장의 주인' in html_b)

print("\n[C] 공개 미동의 학생 - 본인 시점(실명·순위 노출) vs 타인 시점(익명)")
login_as(user_c_id)
resp_c_self = client.get(f'/student/mileage/ranking?season={season}')
content_c_self = content_only(resp_c_self.data.decode('utf-8'))
check("본인 시점에서 '나' 라벨 노출", re.search(r'>\s*나\s*<', content_c_self) is not None)
check("본인 시점에서 비공개 상태 안내 노출", '비공개 상태' in content_c_self)
check("본인 시점에서도 실명(테스트순)은 본문에 노출 안 함", '테스트순' not in content_c_self)

login_as(user_b_id)  # 같은 그룹의 다른 학생(B) 시점 = 타인 시점
resp_c_other = client.get(f'/student/mileage/ranking?season={season}')
content_c_other = content_only(resp_c_other.data.decode('utf-8'))
check("타인 시점에서 학년 학습자 익명 표기 노출", f'{student_c_grade} 학습자' in content_c_other)
check("타인 시점에서 실명(테스트순) 본문에 미노출", '테스트순' not in content_c_other)
check("타인 시점에서 닉네임(익명이될철)도 본문에 미노출", '익명이될철' not in content_c_other)

print("\n[D] 닉네임 설정 및 공개 동의 토글 라우트")
login_as(user_a_id)
client.post('/profile/mileage/nickname', data={'nickname': '새싹독서가'}, follow_redirects=True)
client.post('/profile/mileage/consent/A', data={'is_agreed': '1'}, follow_redirects=True)

login_as(user_e_id)
client.post('/profile/mileage/consent/A', data={'is_agreed': '1'}, follow_redirects=True)  # 닉네임 미설정 -> 차단돼야 함

with app.app_context():
    student_a = db.session.get(Student, student_a_id)
    check("닉네임 저장 성공", student_a.nickname == '새싹독서가')
    status_a = msvc.get_consent_status(student_a_id)
    check("닉네임 설정 후 A 동의 성공", status_a['A'] is True)
    status_e = msvc.get_consent_status(student_e_id)
    check("닉네임 미설정 상태에서 A 동의는 차단됨", status_e['A'] is False)

    # 만 14세 미만 차단 확인 (student_e를 이제 미성년으로 바꿔서 재확인)
    student_e = db.session.get(Student, student_e_id)
    today_kst = (datetime.utcnow() + timedelta(hours=9)).date()
    student_e.birth_date = today_kst.replace(year=today_kst.year - 10)
    db.session.commit()

login_as(user_e_id)
client.post('/profile/mileage/nickname', data={'nickname': '어린학생'})
client.post('/profile/mileage/consent/B', data={'is_agreed': '1'}, follow_redirects=True)

with app.app_context():
    status_e2 = msvc.get_consent_status(student_e_id)
    check("만 14세 미만은 본인 동의가 차단됨", status_e2['B'] is False)

print("\n[E] 모바일(375px) 레이아웃 구조 확인 (CSS 클래스 정적 검사)")
check("뱃지 수집판이 항상 3열 고정(grid-cols-3, 좁은 화면에서도 유지)", 'grid grid-cols-3' in html_b)
check("랭킹표가 <table> 대신 세로 카드 목록(오버플로 없음)", '<table' not in html_ar and '<table' not in content_c_other)

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    PointEvent.query.filter(PointEvent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    StudentBadge.query.filter(StudentBadge.student_id.in_(created_student_ids)).delete(synchronize_session=False)
    MileageConsent.query.filter(MileageConsent.student_id.in_(created_student_ids)).delete(synchronize_session=False)
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
