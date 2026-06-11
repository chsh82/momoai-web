# -*- coding: utf-8 -*-
"""최선우 학생 수업 상태 진단"""
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
from app.models import db, Student
from app.models.course import Course, CourseEnrollment

app = create_app()
with app.app_context():
    student = Student.query.filter(Student.name == '최선우').first()
    if not student:
        print("학생을 찾을 수 없습니다.")
        exit()

    print(f"학생: {student.name} (student_id={student.student_id})\n")

    # 전체 수강 현황
    all_enrollments = CourseEnrollment.query.filter_by(student_id=student.student_id).all()
    print(f"전체 수강 레코드: {len(all_enrollments)}건")
    for e in all_enrollments:
        c = e.course
        if not c:
            continue
        target = '초4보260316' in (c.course_code or '') or '초4보260316' in (c.course_name or '')
        marker = ' ◀◀◀ 대상' if target else ''
        print(f"  [{e.status}] {c.course_name}{marker}")
        print(f"         course_code={c.course_code}, course_type={c.course_type}")
        print(f"         is_terminated={c.is_terminated}, status={c.status}")
        print(f"         start_date={c.start_date}, end_date={c.end_date}")
        print(f"         enrollment.status={e.status}")
