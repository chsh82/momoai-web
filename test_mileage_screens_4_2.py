#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""4단계 2묶음(학부모 화면·관리자/강사 화면) 확인 스크립트

docs/mileage/09_개발지시서_4단계.md의 D/E 항목과 사용자 추가 지시 5가지를
실제 렌더링된 HTML/라우트 응답으로 확인한다. 테스트로 만든 데이터는
스크립트 마지막에 전부 삭제한다.

주의: test_mileage_screens_4_1.py에서 확인한 대로, DB 준비/조회는 짧은
`with app.app_context():` 블록 안에서만 하고 client.get()/post() 호출은
그 블록 밖에서 한다(그렇지 않으면 Flask가 기존 컨텍스트(g)를 재사용해
로그인 사용자가 안 바뀌는 문제가 있었다).
"""
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
from app.models.parent_student import ParentStudent
from app.models.essay import Essay
from app.models.community import Post
from app.models.mileage import PointEvent, StudentBadge, MileageConsent
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


created_user_ids = []
created_student_ids = []
created_essay_ids = []
created_post_ids = []


def make_user(name, role, role_level):
    user = User(user_id=str(uuid.uuid4()), email=f'{uuid.uuid4().hex[:8]}@test.local',
                name=name, role=role, role_level=role_level, is_active=True)
    user.set_password('test1234')
    db.session.add(user)
    db.session.flush()
    created_user_ids.append(user.user_id)
    return user.user_id


def make_student(name, grade='초5', nickname=None, age=16, user_id=None):
    today_kst = (datetime.utcnow() + timedelta(hours=9)).date()
    birth_date = today_kst.replace(year=today_kst.year - age)
    teacher_id = user_id or created_user_ids[0]
    student = Student(teacher_id=teacher_id, user_id=user_id, name=name,
                       grade=grade, nickname=nickname, birth_date=birth_date, status='active')
    db.session.add(student)
    db.session.flush()
    db.session.commit()
    created_student_ids.append(student.student_id)
    return student.student_id


def make_essay(student_id, teacher_id):
    essay = Essay(student_id=student_id, user_id=teacher_id, title='테스트 첨삭',
                  original_text='본문', grade='초5', status='reviewing')
    db.session.add(essay)
    db.session.commit()
    created_essay_ids.append(essay.essay_id)
    return essay.essay_id


print("=" * 70)
print("4-2 화면 확인 스크립트 (학부모 화면 / 관리자·강사 화면)")
print("=" * 70)

with app.app_context():
    teacher_id = make_user('테스트강사', 'teacher', 4)
    admin_id = make_user('테스트관리자', 'admin', 1)
    parent_id = make_user('테스트학부모', 'parent', 4)

    child_full_id = make_student('테스트자녀풀', nickname='자녀닉네임')
    child_view_id = make_student('테스트자녀뷰온리')
    stranger_id = make_student('테스트타인학생')

    db.session.add(ParentStudent(parent_id=parent_id, student_id=child_full_id,
                                 permission_level='full', is_active=True))
    db.session.add(ParentStudent(parent_id=parent_id, student_id=child_view_id,
                                 permission_level='view_only', is_active=True))
    db.session.commit()

    # EX01 주 3명 상한 테스트용 학생 4명 + 각자 essay 1건
    ex01_student_ids = [make_student(f'EX01학생{i}') for i in range(4)]
    ex01_essay_ids = [make_essay(sid, teacher_id) for sid in ex01_student_ids]

    # 우수질문 테스트용 post (질문 카테고리, 학생 계정 작성)
    q_student_user_id = make_user('테스트질문학생계정', 'student', 5)
    q_student_id = make_student('테스트질문학생', user_id=q_student_user_id)
    post = Post(post_id=str(uuid.uuid4()), user_id=q_student_user_id,
                title='질문입니다', content='내용', category='question')
    db.session.add(post)
    db.session.commit()
    post_id = post.post_id
    created_post_ids.append(post_id)

    # 1) 닉네임 미설정 + 공개 동의(A) 기록이 있는 상태(라우트를 거치지 않고
    # 직접 DB에 넣음) - A항목과 무관하게 실명+학년으로 표시되는지 확인
    # (2026-08-30 결정사항으로 A 기반 익명 처리 폐지, nickname도 더는 참조 안 함)
    nickname_test_id = make_student('테스트닉네임없음')
    # 랭킹은 RANKING_FIRST_SEASON(2026-09) 이후 시즌만 집계하므로, occurred_at을
    # 명시하지 않으면(오늘 날짜=8월) 항상 빈 결과가 나온다(2026-08-30 결정사항).
    msvc.award_points(nickname_test_id, 'RW01', 'essay', f'nick-{uuid.uuid4().hex[:8]}',
                      occurred_at=datetime(2026, 9, 1, 12, 0, 0))
    db.session.add(MileageConsent(student_id=nickname_test_id, consent_type='A', is_agreed=True,
                                  agreed_by_user_id=nickname_test_id, agreed_by_relation='self',
                                  doc_version='v1.0'))
    db.session.commit()

    from app.services import ranking_service
    season = msvc.get_season(datetime(2026, 9, 1, 12, 0, 0))
    student_grade = db.session.get(Student, nickname_test_id).grade
    live = ranking_service.build_ranking(season, finalize=False)
    row = next((r for r in live if r['student_id'] == nickname_test_id), None)

print("\n[1] 닉네임 미설정 학생도 실명+학년으로 표시됨")
check("anonymous 키가 결과에 없음(익명 처리 폐지)", row is not None and 'anonymous' not in row)
check("닉네임 미설정이어도 실명+학년으로 표시", row is not None and row['display_name'] == f'테스트닉네임없음 {student_grade}')

print("\n[2] 학부모 접근 통제 - 자녀가 아닌 student_id 직접 접근 차단")
login_as(parent_id)

# base.html이 플래시 메시지를 전역으로 렌더링하지 않아(children.html 등 일부
# 템플릿만 표시) 리다이렉트 후 화면 문구 대신 "차단되어 다른 페이지로
# 리다이렉트되는지 + 실제 데이터가 안 새는지"로 확인한다.
r = client.get(f'/parent/children/{stranger_id}/mileage')
check("타인 학생 마일리지는 200이 아니라 리다이렉트로 차단됨", r.status_code == 302)
r_followed = client.get(f'/parent/children/{stranger_id}/mileage', follow_redirects=True)
html = r_followed.data.decode('utf-8')
check("타인 학생 정보(이름)가 응답에 없음", '테스트타인학생' not in html)

r2 = client.post(f'/parent/children/{stranger_id}/mileage/nickname', data={'nickname': '해킹시도'}, follow_redirects=True)
with app.app_context():
    stranger = db.session.get(Student, stranger_id)
    check("타인 학생 닉네임 POST가 차단되어 DB 변경 없음", stranger.nickname is None)

r3 = client.get(f'/student/mileage/ranking?student_id={stranger_id}')
check("타인 학생 id로 랭킹 접근 시 200이 아니라 리다이렉트로 차단됨", r3.status_code == 302)

# 정상 케이스(본인 자녀)는 통과해야 함
r4 = client.get(f'/parent/children/{child_full_id}/mileage')
check("본인 자녀(full) 마일리지 조회는 정상 200", r4.status_code == 200)
check("본인 자녀 이름이 응답에 노출됨(부모 본인 시점)", '테스트자녀풀' in r4.data.decode('utf-8'))

# view_only는 조회는 되지만 수정은 막혀야 함
r5 = client.get(f'/parent/children/{child_view_id}/mileage')
html5 = r5.data.decode('utf-8')
check("view_only 자녀도 조회는 가능", r5.status_code == 200)
check("view_only 안내 문구 노출", '조회 권한만 있어' in html5)
r6 = client.post(f'/parent/children/{child_view_id}/mileage/nickname', data={'nickname': '몰래변경'}, follow_redirects=True)
with app.app_context():
    child_view = db.session.get(Student, child_view_id)
    check("view_only 자녀 닉네임 변경은 차단됨", child_view.nickname is None)

print("\n[3] 우수답안(EX01) 선정 버튼 - 잔여 횟수 항상 표시 + 0회 시 비활성화")
login_as(teacher_id)

with app.app_context():
    status0 = msvc.get_ex01_selection_status(teacher_id, 'essay', ex01_essay_ids[0])
check("선정 전 잔여 인원 3명", status0['remaining'] == 3 and status0['can_select'] is True)

# GET 화면에서 선정 전에도 잔여 인원이 보여야 한다(눌러보기 전에 알아야 함)
r = client.get(f'/essays/{ex01_essay_ids[0]}/manual-correction')
html = r.data.decode('utf-8')
check("첫 학생 화면에 잔여 인원 3명 표시", '이번 주 남은 선정 가능 인원: 3명' in html)

for i in range(3):
    client.post(f'/essays/{ex01_essay_ids[i]}/select-excellent', follow_redirects=True)

with app.app_context():
    ex01_count = PointEvent.query.filter_by(activity_code='EX01', entry_type='award').filter(
        PointEvent.status != 'cancelled', PointEvent.student_id.in_(ex01_student_ids)
    ).count()
check("3명까지는 정상 선정됨", ex01_count == 3)

# 4번째 학생 화면 - 누르기 전에 이미 잔여 0/비활성화 상태를 볼 수 있어야 한다
r = client.get(f'/essays/{ex01_essay_ids[3]}/manual-correction')
html = r.data.decode('utf-8')
check("4번째 학생 화면에 잔여 0명 표시(누르기 전에 확인 가능)", '이번 주 남은 선정 가능 인원: 0명' in html)
check("버튼이 disabled 상태로 렌더링됨", 'disabled' in html)

r = client.post(f'/essays/{ex01_essay_ids[3]}/select-excellent', follow_redirects=True)
html = r.data.decode('utf-8')
check("4번째 선정 시도는 서버에서도 차단(방어적 이중 확인)", '상한을 초과' in html or '이미' in html)
with app.app_context():
    ex01_count_after = PointEvent.query.filter_by(activity_code='EX01', entry_type='award').filter(
        PointEvent.status != 'cancelled', PointEvent.student_id.in_(ex01_student_ids)
    ).count()
check("4번째 학생에게는 실제로 지급되지 않음", ex01_count_after == 3)

# 이미 선정된 첫 학생 화면은 "이미 선정됨" 표시
r = client.get(f'/essays/{ex01_essay_ids[0]}/manual-correction')
html = r.data.decode('utf-8')
check("이미 선정된 답안은 '이미 선정됨' 상태로 표시", '이미 우수답안으로 선정된 첨삭입니다' in html)

# 학생 role은 선정 라우트 자체가 차단되어야 함
login_as(q_student_user_id)
r = client.post(f'/essays/{ex01_essay_ids[3]}/select-excellent', follow_redirects=True)
html = r.data.decode('utf-8')
check("학생 계정은 우수답안 선정 라우트 접근이 차단됨", '접근 권한이 없습니다' in html)

print("\n[4] 우수질문(QS02) 선정 - 강사/관리자만, 상한 없음")
login_as(teacher_id)
r = client.post(f'/community/{post_id}/select-question', follow_redirects=True)
html = r.data.decode('utf-8')
check("우수질문 선정 성공", '우수질문으로 선정했습니다' in html)
with app.app_context():
    qs02_awarded = msvc.is_awarded('QS02', 'post', post_id)
check("QS02 적립 확인됨", qs02_awarded is True)

login_as(q_student_user_id)
r = client.post(f'/community/{post_id}/select-question', follow_redirects=True)
html = r.data.decode('utf-8')
check("학생 계정은 우수질문 선정도 차단됨", '접근 권한이 없습니다' in html)

print("\n[5] 관리자 포인트 수동 지급·회수 - 사유 필수 + 원장 기록")
login_as(admin_id)

r = client.post(f'/admin/mileage/students/{ex01_student_ids[0]}/grant',
                data={'points': '300', 'reason': ''}, follow_redirects=True)
html = r.data.decode('utf-8')
check("사유 없이 지급 시도하면 차단", '지급 사유는 필수입니다' in html)

r = client.post(f'/admin/mileage/students/{ex01_student_ids[0]}/grant',
                data={'points': '300', 'reason': '이벤트 참여 보상'}, follow_redirects=True)
html = r.data.decode('utf-8')
check("사유와 함께 지급하면 성공", '300점을 지급했습니다' in html)

with app.app_context():
    ev01_event = PointEvent.query.filter_by(
        student_id=ex01_student_ids[0], activity_code='EV01', entry_type='award'
    ).first()
check("EV01 지급 건에 지급자(granted_by)가 기록됨", ev01_event is not None and ev01_event.granted_by == admin_id)
check("EV01 지급 건에 사유(memo)가 기록됨", ev01_event is not None and ev01_event.memo == '이벤트 참여 보상')

r = client.post(f'/admin/mileage/students/{ex01_student_ids[0]}/cancel/{ev01_event.event_id}',
                data={'reason': ''}, follow_redirects=True)
html = r.data.decode('utf-8')
check("사유 없이 취소 시도하면 차단", '취소 사유는 필수입니다' in html)

r = client.post(f'/admin/mileage/students/{ex01_student_ids[0]}/cancel/{ev01_event.event_id}',
                data={'reason': '중복 지급 확인'}, follow_redirects=True)
html = r.data.decode('utf-8')
check("사유와 함께 취소하면 성공", '취소했습니다' in html)

with app.app_context():
    cancel_event = PointEvent.query.filter_by(
        related_event_id=ev01_event.event_id, entry_type='cancel'
    ).first()
check("취소 건에 취소 사유가 기록됨", cancel_event is not None and cancel_event.cancel_reason == '중복 지급 확인')
check("취소 건에 취소한 관리자(granted_by)가 기록됨", cancel_event is not None and cancel_event.granted_by == admin_id)

# 강사(매니저 미만)는 관리자 지급/모니터링 라우트 접근 불가
login_as(teacher_id)
r = client.post(f'/admin/mileage/students/{ex01_student_ids[0]}/grant',
                data={'points': '300', 'reason': '권한 없는 시도'})
check("강사 권한으로는 EV01 지급 라우트가 403", r.status_code == 403)
r = client.get('/admin/mileage')
check("강사 권한으로는 모니터링 대시보드가 403", r.status_code == 403)

print("\n[6] 관리자 모니터링 화면 요소")
login_as(admin_id)
r = client.get('/admin/mileage')
html = r.data.decode('utf-8')
check("모니터링 대시보드 200", r.status_code == 200)
check("강사별 이번 주 선정 현황에 테스트강사 노출", '테스트강사' in html)
check("테스트강사의 선정 건수 3명 표시", '3 / 3명 선정' in html)
check("최근 적립 내역에 방금 지급/취소한 항목이 보임", 'EV01' in html)

r = client.get(f'/admin/mileage?search=EX01학생')
html = r.data.decode('utf-8')
check("학생 검색 결과 노출", 'EX01학생0' in html)

r = client.get(f'/admin/mileage/students/{ex01_student_ids[0]}')
html = r.data.decode('utf-8')
check("학생 상세 조회 200", r.status_code == 200)
check("EV01 지급 이력이 보임(취소선 처리)", 'line-through' in html)
check("EV01 재량 지급 폼 노출", '재량 지급' in html)

print("\n정리: 테스트 데이터 삭제")
with app.app_context():
    all_student_ids = created_student_ids
    PointEvent.query.filter(PointEvent.student_id.in_(all_student_ids)).delete(synchronize_session=False)
    StudentBadge.query.filter(StudentBadge.student_id.in_(all_student_ids)).delete(synchronize_session=False)
    MileageConsent.query.filter(MileageConsent.student_id.in_(all_student_ids)).delete(synchronize_session=False)
    ParentStudent.query.filter(ParentStudent.parent_id == parent_id).delete(synchronize_session=False)
    Essay.query.filter(Essay.essay_id.in_(created_essay_ids)).delete(synchronize_session=False)
    Post.query.filter(Post.post_id.in_(created_post_ids)).delete(synchronize_session=False)
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
