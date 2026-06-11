# -*- coding: utf-8 -*-
"""오늘 생성된 보강수업 및 원본 수업 타입 확인"""
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
from app.models import db
from app.models.course import Course
from datetime import date, datetime

app = create_app()
with app.app_context():
    from app.models.makeup_request import MakeupClassRequest

    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    print(f"오늘 날짜: {today}\n")

    # 오늘 생성된 보강수업 (MAKEUP 코드)
    makeup_courses = Course.query.filter(
        Course.course_code.like('MAKEUP%')
    ).order_by(Course.created_at.desc()).limit(10).all()

    print(f"최근 MAKEUP 코드 수업 (최대 10건):")
    for c in makeup_courses:
        print(f"  [{c.created_at}] {c.course_name}")
        print(f"    course_type={c.course_type}, grade={c.grade}")
        print(f"    start={c.start_time}, end={c.end_time}, duration={c.duration_minutes}분")

    # 오늘 승인된 보강 신청 + 원본 수업 확인
    print(f"\n{'='*50}")
    approved = MakeupClassRequest.query.filter(
        MakeupClassRequest.status == 'approved',
        MakeupClassRequest.admin_response_date >= today_start
    ).order_by(MakeupClassRequest.admin_response_date.desc()).all()

    print(f"오늘 승인된 보강 신청: {len(approved)}건")
    for r in approved:
        orig = r.requested_course
        student = r.student
        makeup_course = Course.query.get(r.created_makeup_course_id) if r.created_makeup_course_id else None
        print(f"\n  학생: {student.name if student else '?'}")
        print(f"  원본 수업: {orig.course_name if orig else '?'}")
        print(f"    orig.course_type: {orig.course_type if orig else '?'}")
        print(f"    orig.grade: {orig.grade if orig else '?'}")
        print(f"  → 생성된 보강수업: {makeup_course.course_name if makeup_course else '없음'}")
        if makeup_course:
            print(f"    course_type={makeup_course.course_type}, duration={makeup_course.duration_minutes}분")
            print(f"    start={makeup_course.start_time}, end={makeup_course.end_time}")

    # 오늘 생성된 보강 관련 수업 (course_type에 '보강' 포함)
    print(f"\n{'='*50}")
    today_bogang = Course.query.filter(
        Course.course_type.like('%보강%'),
        Course.created_at >= today_start
    ).order_by(Course.created_at.desc()).all()
    print(f"오늘 생성된 '보강' 타입 수업: {len(today_bogang)}건")
    for c in today_bogang:
        print(f"  [{c.created_at}] {c.course_name}")
        print(f"    course_type={c.course_type}, grade={c.grade}, duration={c.duration_minutes}분")
        print(f"    start={c.start_time}, end={c.end_time}")
