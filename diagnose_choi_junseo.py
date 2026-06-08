# -*- coding: utf-8 -*-
"""최준서 학생 학부모 대시보드 데이터 진단"""
import sys, os, logging
sys.path.insert(0, os.path.dirname(__file__))
logging.disable(logging.CRITICAL)
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
from app.models import db, Student, User
from app.models.essay import Essay, EssayResult
from app.models.course import Course, CourseEnrollment
from app.models.attendance import Attendance

app = create_app()
with app.app_context():
    from app.utils.enrollment_utils import get_essay_student_ids

    STUDENT_ID = 'bda01623-0828-47a2-b475-98ea68476564'  # 최준서
    student = Student.query.get(STUDENT_ID)
    if not student:
        print("학생을 찾을 수 없습니다.")
        exit()

    print(f"=== 학생 기본 정보 ===")
    print(f"이름: {student.name}, 학년: {student.grade}, 상태: {student.status}")
    print(f"student_id: {student.student_id}, user_id: {student.user_id}")

    # 1. 수강 현황 (출석률 차트 조건)
    print(f"\n=== 수강 현황 (출석률 차트 조건 확인) ===")
    all_enrollments = CourseEnrollment.query.filter_by(student_id=STUDENT_ID).all()
    print(f"전체 수강: {len(all_enrollments)}건")
    for e in all_enrollments:
        c = e.course
        print(f"  - {c.course_name if c else '?'} | enrollment.status={e.status} | course.is_terminated={c.is_terminated if c else '?'} | course.status={c.status if c else '?'} | total_sessions={c.total_sessions if c else '?'} | attended={e.attended_sessions}")

    active_enrollments = CourseEnrollment.query.filter_by(
        student_id=STUDENT_ID, status='active'
    ).join(Course, CourseEnrollment.course_id == Course.course_id).filter(
        Course.is_terminated == False
    ).all()
    print(f"\n→ 출석률 차트에 포함되는 수강(active + 미종료): {len(active_enrollments)}건")
    if active_enrollments:
        total_s = sum(e.course.total_sessions for e in active_enrollments if e.course and e.course.total_sessions)
        attended_s = sum(e.attended_sessions for e in active_enrollments)
        print(f"  total_sessions 합계: {total_s}, attended_sessions 합계: {attended_s}")
        if total_s > 0:
            print(f"  → 출석률: {attended_s/total_s*100:.1f}% (차트에 표시됨)")
        else:
            print(f"  → total_sessions=0 이므로 차트에서 제외됨")
    else:
        print(f"  → 조건 미충족 → 출석률 차트에 표시 안 됨")

    # 2. 첨삭 수 (첨삭수 차트 조건)
    print(f"\n=== 첨삭 수 (첨삭수 차트 조건 확인) ===")
    essay_count_direct = Essay.query.filter_by(student_id=STUDENT_ID).count()
    essay_sids = get_essay_student_ids(student)
    essay_count_all = Essay.query.filter(Essay.student_id.in_(essay_sids)).count()
    print(f"직접 조회(student_id={STUDENT_ID[:8]}...): {essay_count_direct}건")
    print(f"get_essay_student_ids 조회(sids={essay_sids}): {essay_count_all}건")
    print(f"→ 대시보드 첨삭수 차트는 직접 조회 기준 → {'표시됨' if essay_count_direct > 0 else '표시 안 됨'}")

    # 3. 점수 데이터 (점수 그래프 조건)
    print(f"\n=== 점수 데이터 (점수 그래프 조건 확인) ===")
    recent_scores = db.session.query(Essay, EssayResult)\
        .join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
        .filter(
            Essay.student_id.in_(essay_sids),
            EssayResult.total_score.isnot(None)
        ).order_by(Essay.completed_at.desc()).limit(10).all()
    print(f"점수 있는 첨삭: {len(recent_scores)}건")
    for e, r in recent_scores:
        print(f"  - {e.title[:30]} | {r.total_score}점 | {e.completed_at}")
    print(f"→ 점수 그래프: {'표시됨' if recent_scores else '표시 안 됨'}")
