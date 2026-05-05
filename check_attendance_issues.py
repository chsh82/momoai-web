"""
출결 데이터 이상 케이스 진단 스크립트
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.models.course import Course, CourseSession, CourseEnrollment
from app.models.attendance import Attendance
from app.models.student import Student
from datetime import date
from collections import defaultdict

app = create_app()

with app.app_context():
    today = date.today()
    issues = []

    # ── 1. 보강수업 중 출결 레코드 누락 ──────────────────────────
    print("=" * 60)
    print("[1] 보강수업 중 출결 레코드 누락")
    print("=" * 60)
    makeup_courses = Course.query.filter_by(course_type='보강수업').all()
    missing_count = 0
    for course in makeup_courses:
        if not course.start_date or course.start_date > today:
            continue
        for enrollment in CourseEnrollment.query.filter_by(course_id=course.course_id, status='active').all():
            for session in CourseSession.query.filter_by(course_id=course.course_id).all():
                if session.session_date > today:
                    continue
                exists = Attendance.query.filter_by(
                    session_id=session.session_id,
                    student_id=enrollment.student_id
                ).first()
                if not exists:
                    student = Student.query.get(enrollment.student_id)
                    print(f"  ❌ [{session.session_date}] {course.course_name} | {student.name if student else '?'} | 레코드 없음")
                    missing_count += 1
    if missing_count == 0:
        print("  ✅ 누락 없음")

    # ── 2. 같은 날짜에 동일 학생 출결 레코드 2개 이상 ──────────
    print()
    print("=" * 60)
    print("[2] 동일 학생 동일 날짜 출결 중복")
    print("=" * 60)
    all_students = Student.query.all()
    dup_count = 0
    for student in all_students:
        records = (Attendance.query
                   .join(CourseSession, Attendance.session_id == CourseSession.session_id)
                   .filter(Attendance.student_id == student.student_id,
                           CourseSession.session_date <= today)
                   .all())
        by_date = defaultdict(list)
        for r in records:
            by_date[r.session.session_date].append(r)
        for d, recs in by_date.items():
            if len(recs) >= 2:
                print(f"  ⚠️  {student.name} | {d} | {len(recs)}건:")
                for r in recs:
                    course = r.session.course
                    print(f"      attendance_id={r.attendance_id[:8]} status={r.status} 수업={course.course_name}")
                dup_count += 1
    if dup_count == 0:
        print("  ✅ 중복 없음")

    # ── 3. 과거 보강수업 세션이 scheduled 상태 (미완료) ─────────
    print()
    print("=" * 60)
    print("[3] 과거 보강수업 세션 미완료 (scheduled/cancelled)")
    print("=" * 60)
    past_makeup_sessions = (CourseSession.query
                            .join(Course, CourseSession.course_id == Course.course_id)
                            .filter(Course.course_type == '보강수업',
                                    CourseSession.session_date <= today,
                                    CourseSession.status != 'completed')
                            .all())
    if not past_makeup_sessions:
        print("  ✅ 없음")
    for s in past_makeup_sessions:
        att_count = Attendance.query.filter_by(session_id=s.session_id).count()
        print(f"  [{s.session_date}] {s.course.course_name} | status={s.status} | 출결레코드={att_count}개")

    # ── 요약 ─────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"요약: 누락={missing_count}건 | 중복={dup_count}건 | 미완료보강세션={len(past_makeup_sessions)}건")
    print("=" * 60)
