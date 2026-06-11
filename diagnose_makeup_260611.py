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
from datetime import date

app = create_app()
with app.app_context():
    from app.models.makeup_request import MakeupClassRequest

    today = date.today()
    print(f"오늘 날짜: {today}\n")

    # 오늘 생성된 보강수업 조회
    makeup_courses = Course.query.filter(
        Course.course_code.like('MAKEUP%'),
        Course.start_date == today
    ).order_by(Course.created_at.desc()).all()

    print(f"오늘 생성된 보강수업: {len(makeup_courses)}건")
    for c in makeup_courses:
        print(f"\n  [보강수업] {c.course_name}")
        print(f"    course_type: {c.course_type}")
        print(f"    grade: {c.grade}")
        print(f"    start_time: {c.start_time}, end_time: {c.end_time}")
        print(f"    duration_minutes: {c.duration_minutes}")
        print(f"    price_per_session: {c.price_per_session}")

    # 오늘 승인된 보강 신청 + 원본 수업 확인
    print(f"\n{'='*50}")
    approved = MakeupClassRequest.query.filter(
        MakeupClassRequest.status == 'approved',
        MakeupClassRequest.admin_response_date >= str(today)
    ).order_by(MakeupClassRequest.admin_response_date.desc()).all()

    print(f"오늘 승인된 보강 신청: {len(approved)}건")
    for r in approved:
        orig = r.requested_course
        student = r.student
        print(f"\n  학생: {student.name if student else '?'}")
        print(f"  원본 수업: {orig.course_name if orig else '?'}")
        print(f"    orig.course_type: {orig.course_type if orig else '?'}")
        print(f"    orig.grade: {orig.grade if orig else '?'}")
        print(f"    orig.start_time: {orig.start_time if orig else '?'}, orig.end_time: {orig.end_time if orig else '?'}")
