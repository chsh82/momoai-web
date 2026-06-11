# -*- coding: utf-8 -*-
"""특정 보강수업 확인"""
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
from app.models.course import Course, CourseSession

app = create_app()
with app.app_context():
    c = Course.query.filter_by(course_code='MAKEUP2606125a85a165').first()
    if not c:
        print("수업을 찾을 수 없습니다.")
        exit()

    print(f"수업명: {c.course_name}")
    print(f"course_type: {c.course_type}")
    print(f"grade: {c.grade}")
    print(f"start_time: {c.start_time}, end_time: {c.end_time}")
    print(f"duration_minutes: {c.duration_minutes}")
    print(f"start_date: {c.start_date}")

    sessions = CourseSession.query.filter_by(course_id=c.course_id).all()
    for s in sessions:
        print(f"세션: {s.session_date} {s.start_time}~{s.end_time}")
