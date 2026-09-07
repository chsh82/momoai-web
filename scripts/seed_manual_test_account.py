#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""학부모 사용 설명서 스크린샷용(scripts/capture-parent-manual.js) 테스트
학부모+가짜 학생 계정을 만든다.

실제 가족과 완전히 무관한 데이터만 만든다:
  - 학생/수업의 teacher_id는 admin(시스템 관리자) 계정 소유로 둬서, 실제
    강사의 수업 목록/출결 관리 화면에 이 가짜 데이터가 섞여 들어가지 않게
    한다(격리).
  - 수업은 새로 만든 전용 course(정원 1명, "체험단")라 기존 반 출석률/
    통계에도 영향이 없다.

멱등: MANUAL_TEST_PARENT_EMAIL 계정이 이미 있으면 아무것도 만들지 않고
그 계정 정보만 출력한다(재실행 안전).

실행 (프로덕션 서버에서, venv 활성화 후):
    FLASK_ENV=production python scripts/seed_manual_test_account.py
"""
from __future__ import annotations

import io
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from app.models.user import User
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.course import Course, CourseEnrollment, CourseSession
from app.models.attendance import Attendance
from app.models.payment import Payment
from app.models.essay import Essay, EssayVersion, EssayResult
from app.models.essay_score import EssayScore

PARENT_EMAIL = 'manual-test-parent@momoai.kr'
PARENT_PW = 'ManualTest2026!'
PARENT_NAME = '테스트학부모'
STUDENT_NAME = '테스트학생'
ADMIN_EMAIL = 'admin@momoai.com'

THINKING_LABELS = ['요약', '비교', '적용', '평가', '비판', '문제해결', '자료해석', '견해제시', '종합']
INTEGRATED_LABELS = ['결론', '구조논리', '표현명료', '문제인식', '개념정보', '목적적절', '관점다각', '심층성', '완전성']

SAMPLE_ESSAY_TEXT = (
    "요즘 우리 반에서는 재활용 분리수거를 두고 이야기가 많다. 어떤 친구들은 귀찮다고 "
    "그냥 버리고, 어떤 친구들은 꼼꼼히 나눠서 버린다. 나는 분리수거가 조금 번거롭더라도 "
    "꼭 해야 한다고 생각한다. 왜냐하면 우리가 지금 버리는 쓰레기가 결국 우리가 사는 "
    "동네와 지구 전체에 영향을 주기 때문이다. 작은 습관 하나가 나중에는 큰 차이를 "
    "만든다고 배웠다. 그래서 나는 앞으로도 귀찮음보다 책임감을 먼저 생각하려고 한다."
)


def build_manual_html(total_score, thinking, integrated):
    def rows(labels, scores, cls):
        out = []
        for label in labels:
            out.append(f'<div class="{cls}"><span>{label}</span><span>{scores[label]}</span></div>')
        return ''.join(out)

    return f"""<div style="font-family:sans-serif;max-width:720px;margin:0 auto;padding:24px">
<h2>MOMOAI 논술 분석 리포트 (샘플)</h2>
<p>이 첨삭은 학부모 사용 설명서 스크린샷용으로 만든 샘플 데이터입니다.</p>
<h3>총점: {total_score}점</h3>
<h4>사고유형</h4>
{rows(THINKING_LABELS, thinking, 'row')}
<h4>통합지표</h4>
{rows(INTEGRATED_LABELS, integrated, 'row')}
<h4>선생님 코멘트</h4>
<p>주제에 대한 자신의 생각을 명확하게 제시했고, 그 근거도 설득력 있게 연결했습니다.
다음에는 반대 의견도 함께 다뤄보면 글이 더 풍부해질 거예요.</p>
</div>"""


def main():
    app = create_app('production' if '--production' in sys.argv else 'development')
    with app.app_context():
        existing = User.query.filter_by(email=PARENT_EMAIL).first()
        if existing:
            print(f'이미 존재합니다: {PARENT_EMAIL} / 비밀번호는 최초 생성 시에만 출력됩니다.')
            student = Student.query.filter_by(name=STUDENT_NAME, teacher_id=existing.user_id).first()
            print(f'학생: {student.name if student else "(없음)"}')
            return

        admin = User.query.filter_by(email=ADMIN_EMAIL).first()
        if admin is None:
            print(f'오류: 관리자 계정({ADMIN_EMAIL})을 찾을 수 없습니다.')
            sys.exit(1)

        # 1. 학부모 계정
        parent = User(
            email=PARENT_EMAIL, name=PARENT_NAME, role='parent', role_level=4,
            is_active=True,
        )
        parent.set_password(PARENT_PW)
        db.session.add(parent)
        db.session.flush()

        # 2. 학생 (admin 소유 - 실제 강사 roster와 격리)
        student = Student(
            teacher_id=admin.user_id, name=STUDENT_NAME, grade='중1',
            school='(설명서용 테스트)', status='active',
        )
        db.session.add(student)
        db.session.flush()

        # 3. 학부모-학생 연결
        db.session.add(ParentStudent(
            parent_id=parent.user_id, student_id=student.student_id,
            relation_type='parent', permission_level='full', is_active=True,
        ))

        # 4. 전용 테스트 수업 (정원 1명, admin 소유)
        today = date.today()
        weekday = today.weekday()
        course = Course(
            course_name='테스트 체험 수업(설명서용)',
            course_code=f'TEST-MANUAL-{today.strftime("%y%m%d")}',
            grade='중1', course_type='체험단', is_terminated=False,
            availability_status='available', max_students=1,
            teacher_id=admin.user_id, weekday=weekday,
            start_time=time(17, 0), end_time=time(18, 0), duration_minutes=60,
            start_date=today - timedelta(days=21), end_date=today + timedelta(days=21),
            price_per_session=50000, total_sessions=8, status='active',
            makeup_class_allowed=True, created_by=admin.user_id,
        )
        db.session.add(course)
        db.session.flush()

        # 5. 세션 3회(과거) - 출석/지각/출석
        session_dates = [today - timedelta(days=14), today - timedelta(days=7), today - timedelta(days=1)]
        session_statuses = ['present', 'late', 'present']
        sessions = []
        for i, sdate in enumerate(session_dates, start=1):
            s = CourseSession(
                course_id=course.course_id, session_number=i, session_date=sdate,
                start_time=time(17, 0), end_time=time(18, 0),
                topic=f'{i}회차 - 설명서용 샘플 수업', status='completed',
                attendance_checked=True, attendance_checked_at=datetime.utcnow(),
                attendance_checked_by=admin.user_id,
            )
            db.session.add(s)
            sessions.append(s)
        db.session.flush()

        # 6. 수강 등록
        enrollment = CourseEnrollment(
            course_id=course.course_id, student_id=student.student_id,
            status='active', payment_status='paid', paid_sessions=3,
            payment_cycle='monthly', weekly_fee=50000,
            attended_sessions=2, absent_sessions=0, late_sessions=1,
        )
        db.session.add(enrollment)
        db.session.flush()

        # 7. 출석 기록
        for s, status in zip(sessions, session_statuses):
            db.session.add(Attendance(
                session_id=s.session_id, student_id=student.student_id,
                enrollment_id=enrollment.enrollment_id, status=status,
                checked_at=datetime.combine(s.session_date, time(18, 5)),
                checked_by=admin.user_id, checkin_method='manual',
                participation_score=4, comprehension_score=4,
            ))

        # 8. 결제 - 완료 1건, 미납 1건
        db.session.add(Payment(
            enrollment_id=enrollment.enrollment_id, course_id=course.course_id,
            student_id=student.student_id, amount=150000, original_amount=150000,
            payment_type='tuition', payment_period='monthly', sessions_covered=3,
            from_session=1, to_session=3,
            period_start=today - timedelta(days=21), period_end=today - timedelta(days=1),
            weekly_fee=50000, weeks_count=3, payment_method='card', status='completed',
        ))
        db.session.add(Payment(
            enrollment_id=enrollment.enrollment_id, course_id=course.course_id,
            student_id=student.student_id, amount=200000, original_amount=200000,
            payment_type='tuition', payment_period='monthly', sessions_covered=4,
            from_session=4, to_session=7,
            period_start=today, period_end=today + timedelta(days=27),
            weekly_fee=50000, weeks_count=4, payment_method='card', status='pending',
        ))

        # 9. 에세이 - 완료 1건(점수/코멘트 포함) + 진행중 1건
        thinking_scores = {'요약': 8.0, '비교': 7.5, '적용': 7.0, '평가': 8.5, '비판': 7.0,
                            '문제해결': 8.0, '자료해석': 7.5, '견해제시': 8.5, '종합': 8.0}
        integrated_scores = {'결론': 8.5, '구조논리': 7.5, '표현명료': 8.0, '문제인식': 8.0,
                              '개념정보': 7.5, '목적적절': 8.0, '관점다각': 7.0, '심층성': 7.5, '완전성': 8.0}
        total_score = round(0.5 * (sum(thinking_scores.values()) / 9 * 10) +
                             0.5 * (sum(integrated_scores.values()) / 9 * 10), 1)

        essay_done = Essay(
            student_id=student.student_id, user_id=admin.user_id,
            title='분리수거, 귀찮아도 해야 하는 이유', original_text=SAMPLE_ESSAY_TEXT,
            grade='중1', essay_type='basic', status='completed',
            course_id=course.course_id, session_id=sessions[-1].session_id,
            session_assigned_auto=False, correction_model='standard',
            current_version=1, is_finalized=True, finalized_at=datetime.utcnow(),
            created_at=datetime.utcnow() - timedelta(days=1),
            completed_at=datetime.utcnow(),
        )
        db.session.add(essay_done)
        db.session.flush()

        html_folder = Path(app.config['HTML_FOLDER'])
        html_folder.mkdir(parents=True, exist_ok=True)
        filename = f'manual_{essay_done.essay_id}_v1.html'
        html_path = str(html_folder / filename)
        html_content = build_manual_html(total_score, thinking_scores, integrated_scores)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        version = EssayVersion(
            essay_id=essay_done.essay_id, version_number=1,
            html_content=html_content, html_path=html_path,
            revision_note='설명서용 샘플 데이터',
        )
        db.session.add(version)
        db.session.flush()

        db.session.add(EssayResult(
            essay_id=essay_done.essay_id, version_id=version.version_id,
            html_path=html_path, total_score=total_score, final_grade='B+',
        ))
        for label, score in thinking_scores.items():
            db.session.add(EssayScore(essay_id=essay_done.essay_id, version_id=version.version_id,
                                       category='사고유형', indicator_name=label, score=score))
        for label, score in integrated_scores.items():
            db.session.add(EssayScore(essay_id=essay_done.essay_id, version_id=version.version_id,
                                       category='통합지표', indicator_name=label, score=score))

        essay_progress = Essay(
            student_id=student.student_id, user_id=admin.user_id,
            title='주말에 있었던 일', original_text=SAMPLE_ESSAY_TEXT[:80] + '...',
            grade='중1', essay_type='basic', status='processing',
            course_id=course.course_id, session_assigned_auto=True,
            correction_model='standard', current_version=1, is_finalized=False,
            created_at=datetime.utcnow(),
        )
        db.session.add(essay_progress)

        db.session.commit()

        print('생성 완료:')
        print(f'  학부모 이메일: {PARENT_EMAIL}')
        print(f'  학부모 비밀번호: {PARENT_PW}')
        print(f'  학생: {STUDENT_NAME} ({student.student_id})')
        print(f'  수업: {course.course_name} ({course.course_code})')
        print(f'  완료된 첨삭 1건(점수 {total_score}점) + 진행 중 첨삭 1건')
        print(f'  출석 3건(출석/지각/출석), 결제 2건(완료/미납)')


if __name__ == '__main__':
    main()
