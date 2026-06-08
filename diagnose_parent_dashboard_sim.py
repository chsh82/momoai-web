# -*- coding: utf-8 -*-
"""권정분(최준서 부모) 대시보드 렌더링 시뮬레이션"""
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
from app.models import db, User
from app.models.course import Course, CourseEnrollment
from app.models.essay import Essay, EssayResult
from app.models.essay_score import EssayScore
from app.utils.enrollment_utils import get_essay_student_ids

app = create_app()
with app.app_context():
    from app.models.parent_student import ParentStudent

    PARENT_USER_ID = '842530cc-12c6-4de3-8d0d-7be6695be554'  # 권정분
    parent = User.query.get(PARENT_USER_ID)
    print(f"=== 학부모: {parent.name if parent else '?'} ===\n")

    parent_relations = ParentStudent.query.filter_by(
        parent_id=PARENT_USER_ID, is_active=True
    ).all()

    # ── routes.py index() 로직 그대로 재현 ──────────────────────────
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta

    children_data = []
    total_enrollments = 0

    for pr in parent_relations:
        child = pr.student
        if child is None:
            print("  [WARN] pr.student is None — 학생 연결 끊김")
            continue

        active_enrollments = CourseEnrollment.query.filter_by(
            student_id=child.student_id, status='active'
        ).join(Course, CourseEnrollment.course_id == Course.course_id).filter(
            Course.is_terminated == False
        ).all()
        total_enrollments += len(active_enrollments)
        children_data.append({'student': child, 'enrollments': active_enrollments})

    children = [d['student'] for d in children_data]
    print(f"children: {[c.name for c in children]}")
    print(f"total_enrollments: {total_enrollments}\n")

    # 출석률 차트
    child_names = []
    child_attendance_rates = []
    for child in children:
        enrollments = CourseEnrollment.query.filter_by(
            student_id=child.student_id, status='active'
        ).join(Course, CourseEnrollment.course_id == Course.course_id).filter(
            Course.is_terminated == False
        ).all()
        if enrollments:
            total_sessions = sum(e.course.total_sessions for e in enrollments
                                 if e.course and e.course.total_sessions and e.course.total_sessions > 0)
            attended_sessions = sum(e.attended_sessions for e in enrollments)
            if total_sessions > 0:
                rate = (attended_sessions / total_sessions) * 100
                child_names.append(child.name)
                child_attendance_rates.append(round(rate, 1))

    print(f"[출석률 차트] child_names={child_names}, rates={child_attendance_rates}")

    # 첨삭수 차트
    child_essay_names = []
    child_essay_counts = []
    for child in children:
        essay_count = Essay.query.filter_by(student_id=child.student_id).count()
        if essay_count > 0:
            child_essay_names.append(child.name)
            child_essay_counts.append(essay_count)

    print(f"[첨삭수 차트] child_essay_names={child_essay_names}, counts={child_essay_counts}")

    # 점수 추이
    children_scores = []
    for child in children:
        _essay_sids = get_essay_student_ids(child)
        recent_scores = db.session.query(Essay, EssayResult)\
            .join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
            .filter(
                Essay.student_id.in_(_essay_sids),
                EssayResult.total_score.isnot(None)
            ).order_by(Essay.completed_at.desc()).limit(10).all()

        score_data = [float(r.total_score) for _, r in reversed(recent_scores)]
        children_scores.append({
            'student_id': child.student_id,
            'name': child.name,
            'score_data': score_data,
            'has_scores': bool(score_data)
        })
        print(f"[점수 그래프] {child.name}: has_scores={bool(score_data)}, scores={score_data}")

    print(f"\n=== 최종 템플릿 변수 요약 ===")
    print(f"child_names (JSON): {json.dumps(child_names)}")
    print(f"child_attendance_rates (JSON): {json.dumps(child_attendance_rates)}")
    print(f"child_essay_names (JSON): {json.dumps(child_essay_names)}")
    print(f"child_essay_counts (JSON): {json.dumps(child_essay_counts)}")
    print(f"children_scores has_scores: {[cs['has_scores'] for cs in children_scores]}")
