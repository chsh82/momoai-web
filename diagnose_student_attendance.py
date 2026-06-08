# -*- coding: utf-8 -*-
"""박건우 학생 출결 데이터 진단 스크립트"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault('FLASK_ENV', 'production')
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from app import create_app
from app.models import db, Student
from app.models.course import CourseEnrollment, Course, CourseSession
from app.models.attendance import Attendance

app = create_app()
with app.app_context():
    # 1. 학생 존재 여부
    students = Student.query.filter(Student.name.like('%박건우%')).all()
    print(f"=== '박건우' 학생 검색 결과: {len(students)}명 ===")
    for s in students:
        print(f"  student_id={s.student_id}, 이름={s.name}, 학년={s.grade}, 상태={s.status}")

    if not students:
        print("→ Student 테이블에 박건우 학생이 없습니다.")
        sys.exit(0)

    for s in students:
        sid = s.student_id
        print(f"\n=== {s.name} ({s.grade}) - student_id: {sid} ===")

        # 2. 수강 현황
        enrollments = CourseEnrollment.query.filter_by(student_id=sid).all()
        print(f"수강 내역: {len(enrollments)}개")
        for e in enrollments:
            course = e.course
            print(f"  - {course.course_name if course else '?'} | 수강상태={e.status} | course_id={e.course_id}")

        # 3. 출결 레코드 수
        total_att = Attendance.query.filter_by(student_id=sid).count()
        print(f"\n전체 출결 레코드: {total_att}건")

        if total_att == 0:
            print("→ 출결 레코드가 전혀 없습니다.")
            continue

        # 4. 상태별 출결 수
        from sqlalchemy import func
        from app.models.attendance import Attendance as Att
        status_counts = db.session.query(Att.status, func.count(Att.attendance_id))\
            .filter_by(student_id=sid).group_by(Att.status).all()
        print("출결 상태별 분포:")
        for status, cnt in status_counts:
            print(f"  {status}: {cnt}건")

        # 5. 세션 상태별 분포
        from app.models.course import CourseSession as CS
        session_status_counts = db.session.query(CS.status, func.count(Att.attendance_id))\
            .join(Att, CS.session_id == Att.session_id)\
            .filter(Att.student_id == sid)\
            .group_by(CS.status).all()
        print("연결된 세션 상태별 분포:")
        for ss, cnt in session_status_counts:
            print(f"  session.status={ss}: {cnt}건")

        # 6. 최근 출결 5건
        recent = Attendance.query.filter_by(student_id=sid)\
            .join(CourseSession, Attendance.session_id == CourseSession.session_id)\
            .order_by(CourseSession.session_date.desc()).limit(5).all()
        print("최근 출결 5건:")
        for r in recent:
            sess = r.session
            print(f"  {sess.session_date} | att.status={r.status} | session.status={sess.status} | course_id={sess.course_id}")
