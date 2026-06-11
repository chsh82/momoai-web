# -*- coding: utf-8 -*-
"""천주안 첨삭 점수 상세 진단"""
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
from app.models.essay import Essay, EssayResult
from app.models.essay_score import EssayScore

app = create_app()
with app.app_context():
    student = Student.query.filter_by(name='천주안').first()
    if not student:
        print("학생을 찾을 수 없습니다.")
        exit()

    essays = Essay.query.filter_by(student_id=student.student_id).order_by(Essay.created_at.desc()).all()
    print(f"천주안 전체 첨삭: {len(essays)}건\n")
    print(f"{'제목':<25} {'status':<12} {'EssayResult':<12} {'total_score':<12} {'EssayScore수'}")
    print("-" * 80)

    has_result_no_score = 0
    has_score_records = 0

    for e in essays:
        result = e.result
        score_count = EssayScore.query.filter_by(essay_id=e.essay_id).count()
        total_score = result.total_score if result else None
        result_exists = result is not None

        if result_exists and total_score is None:
            has_result_no_score += 1
        if score_count > 0:
            has_score_records += 1

        print(f"{(e.title or '')[:24]:<25} {e.status:<12} {'O' if result_exists else 'X':<12} {str(total_score):<12} {score_count}")

    print(f"\n요약:")
    print(f"  EssayResult 있고 total_score=NULL: {has_result_no_score}건")
    print(f"  EssayScore 개별 점수 있음: {has_score_records}건")
