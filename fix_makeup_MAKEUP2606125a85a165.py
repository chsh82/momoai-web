# -*- coding: utf-8 -*-
"""MAKEUP2606125a85a165 수업 시간 3시간으로 수정"""
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
from datetime import datetime, time

app = create_app()
with app.app_context():
    c = Course.query.filter_by(course_code='MAKEUP2606125a85a165').first()
    if not c:
        print("수업을 찾을 수 없습니다.")
        exit()

    new_end = time(22, 0)  # 19:00 + 3시간
    c.end_time = new_end
    c.duration_minutes = 180

    sessions = CourseSession.query.filter_by(course_id=c.course_id).all()
    for s in sessions:
        s.end_time = new_end

    db.session.commit()
    print(f"완료: {c.course_name}")
    print(f"  duration_minutes: {c.duration_minutes}분")
    print(f"  end_time: {c.end_time}")
