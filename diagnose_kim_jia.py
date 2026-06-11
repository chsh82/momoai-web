# -*- coding: utf-8 -*-
"""김지아 학부모 대시보드 데이터 진단"""
import sys, os, logging, json
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
from app.models import db, User, Student
from app.models.course import Course, CourseEnrollment
from app.models.essay import Essay, EssayResult
from app.models.payment import Payment

app = create_app()
with app.app_context():
    from app.models.parent_student import ParentStudent
    from app.utils.enrollment_utils import get_essay_student_ids

    parent = User.query.filter(User.name.like('%김지아%'), User.role == 'parent').first()
    if not parent:
        print("학부모 '김지아'를 찾을 수 없습니다.")
        # 비슷한 이름 검색
        candidates = User.query.filter(User.role == 'parent').all()
        print("전체 학부모 목록:")
        for u in candidates:
            print(f"  {u.name} ({u.user_id})")
        exit()

    print(f"학부모: {parent.name} (user_id={parent.user_id})\n")

    relations = ParentStudent.query.filter_by(parent_id=parent.user_id, is_active=True).all()
    children = [r.student for r in relations if r.student]
    print(f"연결된 자녀: {[c.name for c in children]}")

    for child in children:
        print(f"\n=== 자녀: {child.name} (student_id={child.student_id}) ===")

        # 수강 현황
        enrollments = CourseEnrollment.query.filter_by(
            student_id=child.student_id, status='active'
        ).join(Course, CourseEnrollment.course_id == Course.course_id).filter(
            Course.is_terminated == False
        ).all()
        print(f"  활성 수강: {len(enrollments)}건")
        for e in enrollments:
            c = e.course
            print(f"    - {c.course_name} | total_sessions={c.total_sessions} | attended={e.attended_sessions}")

        # 출석률 차트 조건
        total_s = sum(e.course.total_sessions for e in enrollments if e.course and e.course.total_sessions and e.course.total_sessions > 0)
        attended_s = sum(e.attended_sessions for e in enrollments)
        if total_s > 0:
            print(f"  출석률 차트: {attended_s}/{total_s} = {attended_s/total_s*100:.1f}% ✅")
        else:
            print(f"  출석률 차트: total_sessions=0 → 차트 미표시 ❌")

        # 첨삭 현황
        essay_count = Essay.query.filter_by(student_id=child.student_id).count()
        print(f"  첨삭수: {essay_count}건 {'✅' if essay_count > 0 else '❌'}")

        # 점수 데이터
        essay_sids = get_essay_student_ids(child)
        scored = db.session.query(Essay, EssayResult)\
            .join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
            .filter(Essay.student_id.in_(essay_sids), EssayResult.total_score.isnot(None))\
            .order_by(Essay.completed_at.desc()).limit(10).all()
        print(f"  점수 데이터: {len(scored)}건 {'✅' if scored else '❌'}")

        # 결제 내역
        from datetime import datetime, timedelta
        six_months_ago = datetime.utcnow() - timedelta(days=180)
        payments = Payment.query.join(
            CourseEnrollment, Payment.enrollment_id == CourseEnrollment.enrollment_id
        ).filter(
            CourseEnrollment.student_id == child.student_id,
            Payment.created_at >= six_months_ago
        ).all()
        print(f"  최근 6개월 결제: {len(payments)}건 {'✅' if payments else '❌'}")
