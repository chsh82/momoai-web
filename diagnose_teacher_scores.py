# -*- coding: utf-8 -*-
"""강사별 점수 입력 현황 분석"""
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
from app.models import db, User
from app.models.essay import Essay, EssayResult
from sqlalchemy import func

app = create_app()
with app.app_context():
    # 강사별 완료 첨삭 집계
    rows = db.session.query(
        Essay.user_id,
        func.count(Essay.essay_id).label('total_completed'),
        func.sum(
            db.case((EssayResult.total_score.isnot(None), 1), else_=0)
        ).label('scored'),
        func.count(Essay.student_id.distinct()).label('total_students'),
    ).join(EssayResult, Essay.essay_id == EssayResult.essay_id, isouter=True)\
     .filter(Essay.status == 'completed')\
     .group_by(Essay.user_id).all()

    # 강사별 점수 있는 학생 수 (별도 쿼리)
    scored_students = db.session.query(
        Essay.user_id,
        func.count(Essay.student_id.distinct()).label('scored_students'),
    ).join(EssayResult, Essay.essay_id == EssayResult.essay_id)\
     .filter(Essay.status == 'completed', EssayResult.total_score.isnot(None))\
     .group_by(Essay.user_id).all()
    scored_map = {r.user_id: r.scored_students for r in scored_students}

    print(f"{'강사명':<16} {'완료첨삭':>6} {'점수입력':>6} {'입력률':>6}  {'담당학생':>6} {'그래프가능':>8} {'학생비율':>8}")
    print("-" * 72)

    results = []
    for r in rows:
        teacher = User.query.get(r.user_id)
        name = teacher.name if teacher else f'(삭제된강사:{r.user_id[:8]})'
        total = r.total_completed or 0
        scored = int(r.scored or 0)
        rate = scored / total * 100 if total else 0
        total_stu = r.total_students or 0
        scored_stu = scored_map.get(r.user_id, 0)
        stu_rate = scored_stu / total_stu * 100 if total_stu else 0
        results.append((name, total, scored, rate, total_stu, scored_stu, stu_rate))

    # 학생 비율 내림차순 정렬
    results.sort(key=lambda x: x[6], reverse=True)

    for name, total, scored, rate, total_stu, scored_stu, stu_rate in results:
        print(f"{name:<16} {total:>6} {scored:>6} {rate:>5.0f}%  {total_stu:>6} {scored_stu:>8} {stu_rate:>7.0f}%")

    print("-" * 72)
    all_total = sum(r[1] for r in results)
    all_scored = sum(r[2] for r in results)
    all_stu = sum(r[4] for r in results)
    all_scored_stu = sum(r[5] for r in results)
    print(f"{'합계':<16} {all_total:>6} {all_scored:>6} {all_scored/all_total*100 if all_total else 0:>5.0f}%  {all_stu:>6} {all_scored_stu:>8} {all_scored_stu/all_stu*100 if all_stu else 0:>7.0f}%")
